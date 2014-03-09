# -*- coding: utf-8 -*-
"""
Created on Sat Mar  8 21:58:59 2014

@author: zah
"""
import unittest

from IPython.utils import traitlets
from labcore.mongotraits import documents

from labcore.mongotraits.tests.base import BaseTest



class TestDocument(documents.Document):
    mstr = traitlets.Unicode(default_value = "axx", db= True)

class TD2(documents.Document):
    xxx = documents.Reference(TestDocument)
    morex = documents.ReferenceList(TestDocument)

class Test_base(BaseTest):
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



if __name__ == '__main__':
    unittest.TestLoader().loadTestsFromTestCase(Test_base).debug()