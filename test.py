# -*- coding: utf-8 -*-
"""
Created on Sat Mar  8 18:50:09 2014

@author: zah
"""
from IPython.utils import traitlets

import documents

documents.connect('test')

class TestDocument(documents.Document):
    mstr = traitlets.Unicode(default_value = "axx", db= True)

class TD2(documents.Document):
    xxx = documents.Reference(TestDocument)

d = TestDocument()
d2 = TD2(xxx = d)
d.save()
d2.save()