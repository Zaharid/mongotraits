# -*- coding: utf-8 -*-
"""
Created on Sat Mar  8 18:21:31 2014

@author: zah
"""
import weakref
import numbers
import cPickle as pickle
import pymongo
from IPython.utils import traitlets
from IPython.utils.py3compat import with_metaclass, string_types

from bson import objectid, dbref

client = None
database = None

def connect(dbname, *args, **kwargs):
    global client, database
    client = pymongo.MongoClient(*args, **kwargs)
    database = client[dbname]

SAME_TYPES = string_types + (numbers.Number, list, tuple, dict,
                             objectid.ObjectId, dbref.DBRef, type(None))


class MongoTraitsError(Exception):
    pass

class ObjectIdTrait(traitlets.Instance):
    def __init__(self, args=None, kw=None, **metadata):
        if args is None and kw is None:
            args = ()
        if not 'db' in metadata:
            metadata['db'] = True
        super(ObjectIdTrait, self).__init__(klass=objectid.ObjectId,
            args = args, kw = kw, allow_none=False, **metadata )


class BaseReference(traitlets.TraitType):
    def __init__(self, *args, **kwargs ):
        if not 'db' in kwargs:
            kwargs['db'] = True
        super(BaseReference, self).__init__(*args, **kwargs)


    def __set__(self, obj, value):
        try:
            value = self.validate(obj, value)
        except traitlets.TraitError:
            value = self.dereference(value)

        super(BaseReference, self).__set__(obj, value)

    def dereference(self, value):
        return self.klass.load(value)
    def ref(self, value):
        return value._id



class Reference(BaseReference, traitlets.Instance):
    pass



class ReferenceList(BaseReference, traitlets.List):
    klass = tuple
    _cast_types = (list, set)
    ref_class = Reference

    def __init__(self, document,  *args, **kwargs):
        trait = self.ref_class(document)
        super(ReferenceList, self).__init__(trait = trait,
            *args, **kwargs)

class Meta(traitlets.MetaHasTraits):

    def __new__(mcls, name, bases, classdict):
        classdict['_idrefs'] = weakref.WeakValueDictionary()
        return super(Meta, mcls).__new__(mcls, name, bases, classdict)

class BaseDocument(with_metaclass(Meta, traitlets.HasTraits)):

    _id = ObjectIdTrait()

    @property
    def id(self):
        return self._id
    @id.setter
    def id(self, value):
        self._id = value

    def __new__(cls, *args, **kwargs):
        inst = super(BaseDocument, cls).__new__(cls, *args,**kwargs)
        inst._db_values = {}
        return inst

    def __init__(self, *args, **kwargs):
        super(BaseDocument,self).__init__(*args, **kwargs)
        self.check_instance()


    def check_instance(self, _id=None):
        if _id is None:
            _id = self._id
        if _id in self.__class__._idrefs:
            raise MongoTraitsError("Trying to instantiate two onjects with the same id")
        if _id is not None:
            self.__class__._idrefs[_id] = self


    @classmethod
    def resolve_instance(cls, kwargsdict, allow_update = False):
        kwargsdict = cls.to_classdict(kwargsdict,allow_update)
        if '_id' in kwargsdict:
            uid =  kwargsdict['_id']
            if uid in cls._idrefs:
                ins = cls._idrefs[uid]
                for key, value in kwargsdict.items():
                    if value != getattr(ins, key):
                        if allow_update:
                            setattr(ins,key, value)
                        else:
                            raise MongoTraitsError("Local and database objects are inconsistent and allow_update is set to false.")
                return ins
        ins = cls(**kwargsdict)
        return ins

    @classmethod
    def to_classdict(cls,kwargsdict, allow_update = False ):
        result = {}
        traits = cls.class_traits(db=True)
        instance_traits = {key:value for (key,value) in traits.items()
            if isinstance(value, traitlets.ClassBasedTraitType) }
        container_traits = {key:value for (key,value) in traits.items()
            if isinstance(value, traitlets.Container) }
        #import pdb;pdb.set_trace()
        print ("container traits:%s"%container_traits)

        for (key, value) in kwargsdict.items():
            if key in container_traits:
                print ("in container traits")
                result[key] = cls.to_container(value,container_traits[key],
                                allow_update)
            elif key in instance_traits:
                result[key] = cls.to_instance(value,instance_traits[key],
                                 allow_update)

            else:
                result[key] = value
        return result

    @classmethod
    def to_instance(cls, value ,trait ,allow_update = False):
        klass = trait.klass
        if hasattr(trait, 'dereference'):
            return trait.dereference(value)
        elif value is None:
            return value
        elif hasattr(klass,'resolve_instance'):
            return klass.resolve_instance(value,
                                          allow_update=allow_update)
        elif issubclass(klass, SAME_TYPES):
            return value
        else:
            return pickle.loads(value)


    @classmethod
    def to_container(cls, value, trait, allow_update):
        _trait =  trait._trait
        if _trait is not None and hasattr(_trait, 'klass'):
            print _trait
            l = []
            for item in value:
                l += [cls.to_instance(item,_trait, allow_update)]
            return l
        else:
           return value

    @property
    def savedict(self):
        savedict={}
        traits = (trait for trait in self.traits().values()
            if trait.get_metadata('db'))

        for trait in traits:
            name = trait.name
            dbname = trait.get_metadata('dbname')
            if dbname is None: dbname = trait.name
            value = self.encode_item(trait, self._trait_values[name])

            savedict[dbname] = value
        return savedict


    def encode_item(self, trait, value):
        if hasattr(trait, 'ref'):
            value = trait.ref(value)
        elif 'savedict' in dir(value):
            value = value.savedict
        elif isinstance(trait, traitlets.Container):
            value = [self.encode_item(trait._trait, elem) for elem in value]
        elif not isinstance(value, SAME_TYPES):
            value = pickle.dumps(value)
        return value

class Document(BaseDocument):

    @classmethod
    def _get_collection_name(cls):
        return cls.__name__

    @classmethod
    def _get_collection(cls):
        return database[cls._get_collection_name()]

    @property
    def collection(self):
        return self._get_collection()

    @property
    def collection_name(self):
        return self._get_collection_name()
    @classmethod
    def find(cls, query=None, allow_update = False):
        for result in cls._get_collection().find(query):
            yield cls.resolve_instance(result,
                                       allow_update=allow_update)

    @classmethod
    def find_one(cls, query=None, allow_update = False):
        result = cls._get_collection().find_one(query)
        if result is None:
            raise MongoTraitsError("There was no element matching the query %r"
            % query)
        return cls.resolve_instance(result,
                                    allow_update=allow_update)

    @classmethod
    def load(cls,_id, allow_update = False):
        if not allow_update and _id in cls._idrefs:
            return cls._idrefs[_id]
        return cls.find_one({'_id':_id}, allow_update = allow_update)

    def refresh(self):
        self.__class__.load(self._id, allow_update = True)


    def save(self):
        self.collection.save(self.savedict)

class EmbeddedDocument(BaseDocument):
    pass