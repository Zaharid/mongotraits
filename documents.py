# -*- coding: utf-8 -*-
"""
Created on Sat Mar  8 18:21:31 2014

@author: zah
"""
import weakref
import numbers
import datetime
from collections import OrderedDict 
try:
    import cPickle as pickle
except ImportError:
    import pickle
from IPython.utils import traitlets
from IPython.utils.py3compat import with_metaclass, string_types
from IPython.utils.importstring import import_item

import pymongo
from bson import objectid, dbref, binary


from labcore.widgets import create_object

client = None
database = None

def connect(dbname, *args, **kwargs):
    global client, database
    client = pymongo.MongoClient(*args, **kwargs)
    database = client[dbname]

SAME_TYPES = string_types + (datetime.datetime, numbers.Number, list, tuple,
                             dict, objectid.ObjectId, dbref.DBRef, type(None))


class MongoTraitsError(Exception):
    pass

def Q(**kwargs):
    return kwargs

class ObjectIdTrait(traitlets.Instance):
    def __init__(self, ins_args=None, ins_kw=None, allow_none = False,
                 **metadata):
        if ins_args is None and ins_kw is None and not allow_none:
            ins_args = ()
        if not 'db' in metadata:
            metadata['db'] = True
        if not 'widget' in metadata:
            metadata['widget'] = None
        super(ObjectIdTrait, self).__init__(klass=objectid.ObjectId,
            args = ins_args, kw = ins_kw, allow_none=allow_none, **metadata )


class BaseReference(traitlets.Instance):
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
        if value is None:
            return None
        return self.klass.load(value)
    def reference(self, value):
        return value._id


class Reference(BaseReference):
    pass

class EmbeddedReference(BaseReference):

    def __init__(self, klass, document, trait_name, *args, **kwargs):
        self.document = document
        self.trait_name = trait_name

        super(EmbeddedReference,self).__init__(klass, *args, **kwargs)

    def instance_init(self,obj):
        super(EmbeddedReference, self).instance_init(obj)
        self.islist = isinstance(self.document.class_traits()[self.trait_name],
                                 traitlets.Container)

    def _resolve_classes(self):
        if isinstance(self.document, string_types):
            self.document = import_item(self.document)
        super(EmbeddedReference, self)._resolve_classes()

    def dereference(self, value):
        if value is None:
            return None
        klass = self.klass
        #TODO: put this in its own method in Document.
        if value in klass._idrefs:
            return klass._idrefs[value]
        c = self.document.collection()
        query = {'{self.trait_name}._id'.format(self=self):value}

        listproj = '.$' if self.islist else ''
        projection = {'{self.trait_name}{listproj}'.format(**locals()):1
        ,"_id":0}
        mgobj = c.find_one(query, projection)['%s'%self.trait_name]
        if self.islist:
            mgobj = mgobj[0]
        return klass.resolve_instance(mgobj)

class TList(traitlets.List):
    """Validades like a list, but type is tuple. Useful until there is an
    eventful list type"""
    klass = tuple
    _cast_types = (list, set)
    
    
#http://stackoverflow.com/questions/16647307/metaclass-cannot-replace-class-dict
class OrderedClass(type):
    @classmethod
    def __prepare__(mcls, name, bases):
        return OrderedDict()

    def __new__(mcls, name, bases, classdict):
        result = super(OrderedClass, mcls).__new__(mcls, name, bases, classdict)
        result._member_names = list(classdict.keys())
        return result


class Meta(traitlets.MetaHasTraits, OrderedClass):
    
    def __new__(mcls, name, bases, classdict):
        classdict['_idrefs'] = weakref.WeakValueDictionary()
        return super(Meta, mcls).__new__(mcls, name, bases, classdict)

class BaseDocument(with_metaclass(Meta, traitlets.HasTraits)):

    _id = ObjectIdTrait()

    db_default = True
    _class_tag = False


    @property
    def id(self):
        return self._id
    @id.setter
    def id(self, value):
        self._id = value

    def __init__(self, *args, **kwargs):
        super(BaseDocument,self).__init__(*args, **kwargs)
        self.check_instance()

    def check_instance(self, _id=None):
        errstr = "Trying to instantiate two onjects with the same id"
        if _id is None:
            _id = self._id
        if _id in self.__class__._idrefs:
            raise MongoTraitsError(errstr)
        if _id is not None:
            self.__class__._idrefs[_id] = self

    @classmethod
    def resolve_instance(cls, kwargsdict, allow_update = False):
        errstr = ("Local and database objects are inconsistent and"
        " allow_update is set to false.")
        if cls._class_tag:
            kwargsdict.pop('_cls')
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
                            raise MongoTraitsError(errstr)
                return ins
        ins = cls(**kwargsdict)
        return ins

    @classmethod
    def to_classdict(cls,kwargsdict, allow_update = False ):
        result = {}
        if cls.db_default:
            traits = cls.class_traits(db=lambda x: x is not False)
        else:
            traits = cls.class_traits(db=True)
        instance_traits = {key:value for (key,value) in traits.items()
            if isinstance(value, traitlets.ClassBasedTraitType) }
                
        container_traits = {key:value for (key,value) in traits.items()
            if isinstance(value, traitlets.Container) }
                
        for (key, value) in kwargsdict.items():
            if key in container_traits:
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
            l = []
            for item in value:
                l += [cls.to_instance(item,_trait, allow_update)]
            return trait.klass(l)
        else:
           return trait.klass(value)

    @property
    def savedict(self):
        savedict={}
        if self.db_default:
            traits = self.traits(db = lambda x: x is not False).values()
        else:
            traits = self.traits(db=lambda x: x).values()

        for trait in traits:
            name = trait.name
            value = self.encode_item(trait, self._trait_values[name])
            savedict[name] = value
        if self._class_tag:
            savedict['_cls'] = self.__class__.__name__
        return savedict

    @staticmethod
    def encode_item(trait, value):
        if value is None:
            return value
        elif hasattr(trait, 'reference'):
            value = trait.reference(value)
        elif 'savedict' in dir(value):
            value = value.savedict
        elif isinstance(trait, traitlets.Container):
            value = [Document.encode_item(trait._trait,elem) for elem in value]
        elif not isinstance(value, SAME_TYPES):
            value = binary.Binary(pickle.dumps(value))
        return value

    @property
    def references(self):
        return self._refs()

    def _refs(self, refs=None):
        if refs is None:
            refs = set()

        def add_ref(value):
            if value is not None and not value in refs:
                refs.add(value)
                value._refs(refs)

        if self.db_default:
            traits = self.traits(db = lambda x: x is not False).values()
        else:
            traits = self.traits(db=lambda x: x).values()

        for trait in traits:
            if (isinstance(trait, BaseReference) or
            (isinstance(trait, traitlets.Instance) and
            issubclass(trait.klass, BaseDocument))):
                value = self._trait_values[trait.name]
                add_ref(value)
            elif isinstance(trait, traitlets.Container):
                _trait =  trait._trait
                if (_trait is not None and
                isinstance(_trait, BaseReference)):
                    items = self._trait_values[trait.name]
                    for value in items:
                        add_ref(value)
        return refs

    @property
    def document_references(self):
        return {ref for ref in self.references if isinstance(ref,Document)}

    def __repr__(self):
        return "<%s: %s>"%(self.__class__.__name__, self._id)
        
    class CreateManager(create_object.CreateManager):
        @property            
        def create_description(self):
            return "Create %s and save" % self.cls.__name__
            
        def new_object(self, button):
            obj = super(BaseDocument.CreateManager, self).new_object(button)
            obj.save()
            return obj

class Document(BaseDocument):

    indb = False
    
    @classmethod
    def collection_name(cls):
        baseindex = cls.__mro__.index(Document) - 1
        if baseindex < 0:
            raise MongoTraitsError("Need to subclass before"
            " getting a collection name.")
        baseclass = cls.__mro__[baseindex]
        return baseclass.__name__

    @classmethod
    def collection(cls):
        if database is None:
            raise MongoTraitsError("Must connect to the database to retrieve "
                "the collection.")
        return database[cls.collection_name()]

    @classmethod
    def _resolve_query(cls, query):
        if query is None:
            if not cls._class_tag:
                return None
            else:
                return {'_cls': cls.__name__}
        query = dict(query)
        for (name,value) in query.items():
            trait = cls.class_traits()[name]
            query[name] = cls.encode_item(trait, value)
        if cls._class_tag:    
            query['_cls'] = cls.__name__
        return query

    @classmethod
    def find(cls, query = None, projection = None, allow_update = False, **kwargs):
        query = cls._resolve_query(query)
        for result in cls.collection().find(query,projection, **kwargs):
            ins =  cls.resolve_instance(result,
                                       allow_update=allow_update)
            ins.indb = True
            yield ins

    @classmethod
    def find_one(cls, query = None, projection = None, allow_update = False, **kwargs):
        query = cls._resolve_query(query)
        result = cls.collection().find_one(query, projection, **kwargs)
        if result is None:
            raise MongoTraitsError(("There was no element matching the query %r"
            " in collection %s.")% (query, cls.collection_name()))
        ins =  cls.resolve_instance(result,
                                    allow_update=allow_update)
        ins.indb = True
        return ins

    @classmethod
    def exists(cls, query):
        query = cls._resolve_query(query)
        res = cls.collection().find(query, limit = 1)
        return res.count(with_limit_and_skip=True) > 0


    @classmethod
    def remove(cls, query = None, **kwargs):
        query = cls._resolve_query(query)
        cls.collection().remove(query, **kwargs)


    @classmethod
    def get_or_create(cls, query = None, projection = None,
                      allow_update = False):
        query = cls._resolve_query(query)
        try:
            return cls.find_one(query, projection, allow_update = False)
        except MongoTraitsError:
            return cls(**query)

    @classmethod
    def load(cls,_id, allow_update = False):
        if not allow_update and _id in cls._idrefs:
            return cls._idrefs[_id]
        return cls.find_one({'_id':_id}, allow_update = allow_update)


    def refresh(self):
        self.__class__.load(self._id, allow_update = True)

    def delete(self):
        self.__class__.remove({'_id' : self._id}, multi = False)

    def save(self, cascade = False):
        if cascade:
            for ref in self.document_references:
                ref.save(cascade = False)
        self.collection().save(self.savedict)
        self.indb = True

class EmbeddedDocument(BaseDocument):
    pass