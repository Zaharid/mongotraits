# -*- coding: utf-8 -*-
"""
Created on Sat Mar  8 18:21:31 2014

@author: zah
"""
import weakref

import pymongo
from IPython.utils import traitlets
from IPython.utils.py3compat import with_metaclass

from bson import objectid, dbref

client = None
database = None

class MongoTraitsError(Exception):
    pass

def connect(dbname, *args, **kwargs):
    global client, database
    client = pymongo.MongoClient(*args, **kwargs)
    database = client[dbname]


class ObjectIdTrait(traitlets.Instance):
    def __init__(self, args=None, kw=None, **metadata):
        if args is None and kw is None:
            args = ()
        if not 'db' in metadata:
            metadata['db'] = True
        super(ObjectIdTrait, self).__init__(klass=objectid.ObjectId,
            args = args, kw = kw, allow_none=False, **metadata )


class BaseReference(traitlets.TraitType):
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
    def __init__(self, klass=None, args=None, kw=None,
                 allow_none=True, **metadata ):
        if not 'db' in metadata:
            metadata['db'] = True
        super(Reference, self).__init__(klass, args, kw, allow_none, **metadata)




class ReferenceList(BaseReference, traitlets.List):
    klass = tuple
    _cast_types = (list, set)
    ref_class = Reference

    def __init__(self, document,  default_value=None, allow_none=True,
                **metadata):
        trait = self.ref_class(document)
        super(ReferenceList, self).__init__(trait = trait,
             default_value=default_value, allow_none=allow_none,
             **metadata)
    def dereference(self, value):
        return tuple(self._trait.dereference(elem) for elem in value)
    def ref(self, value):
        return tuple(elem._id for elem in value)



class Meta(traitlets.MetaHasTraits):

    def __new__(mcls, name, bases, classdict):
        if '_id' in classdict:
            raise ValueError("""This class cannot declare an '_id attribute'.
            It is initialized as the database id""")
        classdict['_id'] = ObjectIdTrait()

        classdict['_id_prop'] = '_id'
        classdict['_idrefs'] = weakref.WeakValueDictionary()

        return super(Meta, mcls).__new__(mcls, name, bases, classdict)

class BaseDocument(with_metaclass(Meta, traitlets.HasTraits)):

    def __new__(cls, *args, **kwargs):
        inst = super(BaseDocument, cls).__new__(cls, *args,**kwargs)
        inst._db_values = {}
        return inst

    def __init__(self, *args, **kwargs):
        super(BaseDocument,self).__init__(*args, **kwargs)
        if self._id in self.__class__._idrefs:
            raise MongoTraitsError("Trying to instantiate two onjects with the same id")
        self.__class__._idrefs[self._id] = self

    @classmethod
    def resolve_instance(cls, allow_update = False ,**kwargs):
        if '_id' in kwargs:
            uid =  kwargs.pop('_id')
            if uid in cls._idrefs:
                ins = cls._idrefs[uid]
                for key, value in kwargs.items():
                    if value != getattr(ins, key):
                        if allow_update:
                            setattr(ins,key, value)
                        else:
                            raise MongoTraitsError("Local and database objects are inconsistent and allow_update is set to false.")
                return ins
        ins = cls(**kwargs)
        return ins

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
                    value = value.savedict()
            savedict[dbname] = value
        return savedict



class Document(BaseDocument):
    @property
    def id(self):
        return self._id
    @id.setter
    def id(self, value):
        self._id = value

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
            yield cls.resolve_instance(allow_update, **result)

    @classmethod
    def find_one(cls, query=None, allow_update = False):
        result = cls._get_collection().find_one(query)
        if result is None:
            raise MongoTraitsError("There was no element matching the query %r"
            % query)
        return cls.resolve_instance(allow_update, **result)

    @classmethod
    def load(cls,_id, allow_update = False):
        if not allow_update and _id in cls._idrefs:
            return cls._idrefs[_id]
        return cls.find_one({'_id':_id}, allow_update = allow_update)

    def refresh(self):
        self.__class__.load(self._id, allow_update = True)


    def save(self):
        self.collection.save(self.savedict)


