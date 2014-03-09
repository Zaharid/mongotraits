# -*- coding: utf-8 -*-
"""
Created on Sat Mar  8 21:58:59 2014

@author: zah
"""
import unittest

from IPython.utils import traitlets
from bson.objectid import ObjectId
from labcore.mongotraits import documents

from labcore.mongotraits.tests.base import BaseTest

class EmbDoc(documents.EmbeddedDocument):
    name = traitlets.Unicode(default_value = "Hello world",db=True)
    value = traitlets.Bool(db=True)


class TestDocument(documents.Document):
    mstr = traitlets.Unicode(default_value = "axx", db= True)
    emb = documents.EmbeddedDocumentTrait(EmbDoc)

class TD2(documents.Document):
    xxx = documents.Reference(TestDocument)
    morex = documents.ReferenceList(TestDocument)

class Test_base(BaseTest):
    def test_toclass(self):
        dic = {u'_id': ObjectId('531c922c1a8d5f4fbc4a8ed7'),
               u'name': u'Hello world', u'value': False}
        self.assertEqual(EmbDoc.to_classdict(dic, base_document = TestDocument), dic)
    def test_a(self):
        doc = TestDocument(mstr = 'xx')
        self.assertTrue(doc.mstr == 'xx')
        self.assertIsNotNone(doc.id)
        doc.save()
        newdoc = TestDocument.find_one()
        self.assertTrue(doc is newdoc)

    def test_refresh(self):
        doc = TestDocument(mstr = 'xx')
        TestDocument._get_collection().save({'_id':doc.id, 'mstr':'xyz'})
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



if __name__ == '__main__':
    unittest.TestLoader().loadTestsFromTestCase(Test_base).debug()