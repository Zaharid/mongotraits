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
            documents.EmbeddedReference(EmbDoc,'TestDocument','moreembs'),
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



if __name__ == '__main__':
    unittest.TestLoader().loadTestsFromTestCase(Test_base).debug()