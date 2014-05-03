# -*- coding: utf-8 -*-
"""
Created on Sat Mar  8 21:59:43 2014

@author: zah
"""

import unittest
from labcore.mongotraits import documents
from labcore.mongotraits.documents import  connect
class BaseTest(unittest.TestCase):
    def setUp(self):
        connect('test')
        documents.client.drop_database('test')

    def tearDown(self):
        documents.client.drop_database('test')