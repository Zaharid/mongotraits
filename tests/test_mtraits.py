# -*- coding: utf-8 -*-
"""
Created on Sat Mar  8 21:58:59 2014

@author: zah
"""
import unittest

from IPython.utils import traitlets
from bson.objectid import ObjectId
from labcore.mongotraits import documents

import numpy as np

from labcore.mongotraits.tests.base import BaseTest

class EmbDoc(documents.EmbeddedDocument):
    name = traitlets.Unicode(default_value = "Hello world",db=True)
    value = traitlets.Bool(db=True)
    ref = documents.Reference(__name__ + ".TestDocument")

class DeferredReference(documents.Document):
    ref = documents.Reference(__name__+'.TestDocument')

class TestDocument(documents.Document):
    mstr = traitlets.Unicode(default_value = "axx", db= True)
    number = traitlets.Float(db=True)
    emb = traitlets.Instance(EmbDoc, db=True)
    moreembs = traitlets.List(traitlets.Instance(EmbDoc), db=True)
    lst = documents.TList(traitlets.Int)

class TD2(documents.Document):
    xxx = documents.Reference(TestDocument)
    morex = traitlets.List(documents.Reference(TestDocument), db=True)
    emblist = traitlets.List(
            documents.EmbeddedReference(EmbDoc,TestDocument,'emb'), db=True
            )
    moreembslist = traitlets.List(
            documents.EmbeddedReference(EmbDoc,
                                        __name__+'.TestDocument','moreembs'),
             db=True)

class NpSave(documents.Document):
    arr = traitlets.Instance(np.ndarray, db=True)

class DocFalseDb(documents.Document):
    db_default = False
    a = traitlets.Int(db = False)
    b = traitlets.Int(db = True)
    c = traitlets.Int()

class DocTrueDb(documents.Document):
    db_default = True
    a = traitlets.Int(db = False)
    b = traitlets.Int(db = True)
    c = traitlets.Int()

class CascadeDoc(documents.Document):
    reflist = documents.TList(documents.Reference(DeferredReference))

class Sub(TestDocument):
    pass

class BaseDoc(documents.Document):
    a = traitlets.Int()
    ref = documents.Reference(__name__+'.BaseDoc')

class ADoc(BaseDoc):
    _class_tag = True

class BDoc(BaseDoc):
    _class_tag = True


class Test_base(BaseTest):
    def test_toclass(self):
        dic = {u'_id': ObjectId('531c922c1a8d5f4fbc4a8ed7'),
               u'name': u'Hello world', u'value': False}
        self.assertEqual(EmbDoc.to_classdict(dic), dic)
    def test_a(self):
        doc = TestDocument(mstr = 'xx')
        self.assertTrue(doc.mstr == 'xx')
        self.assertIsNotNone(doc.id)
        doc.save()
        newdoc = TestDocument.find_one()
        self.assertTrue(doc is newdoc)

    def test_refresh(self):
        doc = TestDocument(mstr = 'xx')
        TestDocument.collection().save({'_id':doc.id, 'mstr':'xyz'})
        self.assertRaises(documents.MongoTraitsError,TestDocument.find_one)
        TestDocument.find_one(allow_update = True)
        self.assertEqual(doc.mstr, 'xyz')
    def test_references(self):
        doc1 = TestDocument(mstr = 'd1')
        doc2 = TestDocument(mstr = 'd2')
        doc3 = TestDocument(mstr = 'd3')
        td = TD2(xxx = doc1, morex= [doc2,doc3])
        td.save()
        doc1.save()
        doc2.save()
        doc3.save()
        del doc1
        del doc2
        del doc3
        del td
        self.assertFalse(TestDocument._idrefs.data)
        new_td2 = TD2.find_one()
        self.assertEqual(len(new_td2.morex),2)
    def test_embdoc(self):
        doc = TestDocument()
        embdoc = EmbDoc()
        embdoc.name = "Good Bye"
        doc.emb = embdoc
        doc.save()
        del doc
        new_doc = TestDocument.find_one()
        self.assertEqual(new_doc.emb.name, "Good Bye")
        self.assertTrue(new_doc.emb is embdoc)
    def test_numpy(self):
        obj = NpSave()
        arr = np.random.normal(size = (100,100))
        obj.arr = arr
        obj.save()
        del obj
        new_obj = NpSave.find_one()
        self.assertTrue(np.all(arr== new_obj.arr))
    def test_embedded_reference(self):
        td = TestDocument()
        embdoc = EmbDoc()
        embdocs = [EmbDoc(name= 'a'), EmbDoc(name='b'), EmbDoc(name='c')]
        td.emb = embdoc
        td.moreembs = embdocs
        td2 = TD2()
        td2.emblist = [embdoc]
        td2.moreembslist = embdocs[1:]
        td.save()
        td2.save()
        del td
        del td2
        new_td2 = TD2.find_one()
        self.assertTrue(new_td2.emblist[0] is embdoc)
        self.assertEqual(new_td2.moreembslist, embdocs[1:])
    def test_find(self):
        for char,num in zip('ZBCDAZZC', '12345677'):
            d = TestDocument(mstr=char, number = float(num))
            d.save()
        del d
        docs1 = list(TestDocument.find({'number':{'$gt':4}}))
        self.assertEqual(len(docs1),4)
        docs2 = list(TestDocument.find({'mstr':'Z'}))
        docs3 = list(TestDocument.find({'mstr':'Z','number':{'$gt':4}}))
        self.assertEqual(set(docs1) & set(docs2), set(docs3))
        proj = list(TestDocument.find(projection = {'mstr':1}))
        self.assertEqual(len(proj),8)

    def test_defred(self):
        d = TestDocument()
        r = DeferredReference(ref = d)
        self.assertTrue(r.ref is d)
    def test_dbdefault(self):
        d1 = DocFalseDb()
        d2 = DocTrueDb()
        self.assertTrue('c' not in d1.savedict)
        self.assertTrue('c' in d2.savedict)
    def test_cast_tuple(self):
        doc = TestDocument()
        doc.lst = [1,2,3]
        doc.save()
        TestDocument.find_one()
    def test_save_cascade(self):
        casdoc = CascadeDoc()
        d1,d2 = TestDocument(name = 'd1'), TestDocument()
        derefs = [DeferredReference(ref=d1),DeferredReference(ref=d2)]
        emb = EmbDoc(ref = d1)
        d1.emb = emb
        casdoc.reflist = derefs
        self.assertEqual(casdoc.references, {d1,d2, emb} | set(derefs))
        casdoc.save(cascade = True)
        del casdoc, d1,d2, derefs, emb
        rec= CascadeDoc.find_one()
        self.assertTrue(rec.reflist[0].ref.emb.ref.name == 'd1')
    def test_find_subclass(self):
        sub = Sub(mstr = "ssub")
        dref = DeferredReference(ref = sub)
        dref.save(cascade = True)
        del dref, sub
        nsub = DeferredReference.find_one()
        self.assertEqual(nsub.ref.mstr, "ssub")
    def test_indb(self):
        doc, doc2, doc3 = TestDocument(), TestDocument(), TestDocument()
        self.assertFalse(doc.indb)
        doc.save()
        doc2.save()
        doc3.save()
        self.assertTrue(doc.indb)
        del doc, doc2, doc3
        ndoc = TestDocument.find_one()
        self.assertTrue(ndoc.indb)
        ndocs = TestDocument.find()
        self.assertTrue(all(d.indb for d in ndocs))
    def test_delete(self):
        doc, doc2, doc3 = TestDocument(mstr='x'),TestDocument(), TestDocument()
        doc.save()
        doc2.save()
        doc3.save()
        did = doc.id
        del doc
        TestDocument.remove({'mstr':'x'})
        self.assertRaises(documents.MongoTraitsError, TestDocument.find_one, {'_id':did})
        doc2.delete()
        del doc2
        self.assertEqual(len(list(TestDocument.find())),1)

    def test_exists(self):
        doc, doc2, doc3 = TestDocument(mstr='x'),TestDocument(), TestDocument()
        doc.save()
        doc2.save()
        doc3.save()
        self.assertTrue(TestDocument.exists({'mstr':'x'}))
        self.assertFalse(TestDocument.exists({'mstr':'xxx'}))

    def test_multi(self):
        base = BaseDoc(a=-1)
        a1,a2,a3 = [ADoc(a = i) for i in (1,2,3)]
        b1,b2,b3 = [BDoc(a = i) for i in (1,2,3)]
        base.save()
        a1.save()
        a2.save()
        a3.save()
        b1.save()
        b2.save()
        b3.save()
        self.assertEqual(len(list(BaseDoc.find())),7)
        self.assertEqual(len(list(ADoc.find())),3)
        self.assertEqual(len(list(BDoc.find())),3)
        ADoc.remove({'a':2})
        self.assertEqual(len(list(ADoc.find())),2)
        self.assertEqual(len(list(BDoc.find())),3)
        b1.ref = a1
        b1.save()
        del b1
        del a1
        b1 = BDoc.find_one({'a':1})
        self.assertIsInstance(b1.ref, ADoc)

    def test_references_resolve_classes(self):
        td = TestDocument()
        dr = DeferredReference(ref = td)
        self.assertIs(dr.ref, td)
        dr.save()
        td.save()
        del td
        del dr
        #Will fail if _resolve_classes is never called.
        class X(documents.Document):
            ref = documents.Reference(__name__+'.TestDocument')
            @classmethod
            def collection_name(cls):
                return 'DeferredReference'
        dr = X.find_one()
        self.assertIsInstance(dr.ref, TestDocument)


if __name__ == '__main__':
    unittest.TestLoader().loadTestsFromTestCase(Test_base).debug()