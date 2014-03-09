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
        obj._db_values[self.name] = self.ref(value)

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

    def dereference(self, value):
        print("Tryind to dereference %s"%value)
        return tuple(self._trait.dereference(elem) for elem in value)
    def ref(self, value):
        return tuple(elem._id for elem in value)

class EmbeddedDocumentTrait(traitlets.Instance):
    def __init__(self, *args, **kwargs):
        if not 'db' in kwargs:
            kwargs['db'] = True
        super(EmbeddedDocumentTrait, self).__init__(*args, **kwargs)
    def __set__(self, obj, value):
        super(EmbeddedDocumentTrait, self).__set__(obj, value)
        if self.__get__(obj) is not None:
            value.base_document = obj.__class__
            value.__class__._idrefs[value.idref_key(value)] = value


            #value.check_instance()


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
        self.base_document = kwargs.pop('base_document', None)
        super(BaseDocument,self).__init__(*args, **kwargs)
        self.check_instance()


    def check_instance(self, _id=None, base_document=None):
        if _id is None:
            _id = self._id
        if base_document is None:
            base_document = self.base_document
        key = self.idref_key(self, _id = _id, base_document = base_document)
        if key in self.__class__._idrefs:
            raise MongoTraitsError("Trying to instantiate two onjects with the same id")
        if key is not None:
            self.__class__._idrefs[key] = self


    @classmethod
    def resolve_instance(cls, kwargsdict, base_document = None, allow_update = False):
        kwargsdict = cls.to_classdict(kwargsdict, base_document,allow_update)
        if '_id' in kwargsdict:
            uid =  kwargsdict['_id']
            idref_key = cls.idref_key(_id = uid, base_document = base_document)
            if idref_key in cls._idrefs:
                ins = cls._idrefs[idref_key]
                for key, value in kwargsdict.items():
                    if value != getattr(ins, key):
                        if allow_update:
                            setattr(ins,key, value)
                        else:
                            raise MongoTraitsError("Local and database objects are inconsistent and allow_update is set to false.")
                return ins
        kwargsdict['base_document'] = base_document
        ins = cls(**kwargsdict)
        return ins

    @staticmethod
    def idref_key(ins=None, _id=None, base_document = None):
        if _id is None:
            return ins._id
        else:
            return _id


    @classmethod
    def to_classdict(cls,kwargsdict, base_document = None, allow_update = False ):
        result = {}
        traits = cls.class_traits(db=True)
        instance_traits = {key:value for (key,value) in traits.items()
            if isinstance(value, traitlets.ClassBasedTraitType) }
        container_traits = {key:value for (key,value) in traits.items()
            if isinstance(value, traitlets.Container) }

        for (key, value) in kwargsdict.items():
            if key in instance_traits:
                result[key] = cls.to_instance(value,instance_traits[key],
                                base_document, allow_update)
            elif key in container_traits:
                result[key] = cls.to_container(value,container_traits[key],
                                base_document, allow_update)
            else:
                result[key] = value
        return result

    @classmethod
    def to_instance(cls, value ,trait, base_document ,allow_update = False):
        klass = trait.klass
        if hasattr(trait, 'dereference'):
            return trait.dereference(value)
        elif value is None:
            return value
        elif hasattr(klass,'resolve_instance'):
            return klass.resolve_instance(value, base_document = base_document,
                                          allow_update=allow_update)
        elif issubclass(klass, SAME_TYPES):
            return value
        else:
            return pickle.loads(value)


    @classmethod
    def to_container(cls, value, trait, base_document, allow_update):
        import pdb;pdb.set_trace()
        _trait =  trait._trait
        if _trait is not None and hasattr(_trait, 'klass'):
            l = []
            for item in value:
                l += [cls.to_instance(item,_trait,base_document, allow_update)]
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
            if name in self._db_values:
                value = self._db_values[name]
            else:
                value = self._trait_values[name]
                if 'savedict' in dir(value):
                    value = value.savedict
                elif not isinstance(value, SAME_TYPES):
                    value = pickle.dumps(value)
            savedict[dbname] = value
        return savedict

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
            yield cls.resolve_instance(result, base_document = cls,
                                       allow_update=allow_update)

    @classmethod
    def find_one(cls, query=None, allow_update = False):
        result = cls._get_collection().find_one(query)
        if result is None:
            raise MongoTraitsError("There was no element matching the query %r"
            % query)
        return cls.resolve_instance(result, base_document=cls,
                                    allow_update=allow_update)

    @classmethod
    def load(cls,_id, allow_update = False):
        key = cls.idref_key(_id = _id)
        if not allow_update and key in cls._idrefs:
            return cls._idrefs[key]
        return cls.find_one({'_id':_id}, allow_update = allow_update)

    def refresh(self):
        self.__class__.load(self._id, allow_update = True)


    def save(self):
        self.collection.save(self.savedict)

class EmbeddedDocument(BaseDocument):
    @staticmethod
    def idref_key(ins=None, _id=None, base_document = None):

        if base_document is None:
            base_document = ins.base_document
        if base_document is None:
            return None
        if _id is None:
            _id = ins._id
        assert(issubclass(base_document, Document))
        return (base_document, _id)


