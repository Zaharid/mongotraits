Mongotraits
===========

A liteweight simple Object Document Manager to connect Python objects to MongoDB, similar to [mongoengine](http://mongoengine.org/)

Features
--------

   * Based on IPython Traitlets.
   * User interface in IPython Notebook for creating and adding objects via the widgetrepr package.
   * Objects with the same id are always the same python object.
   * References are special TraitType subclasses that implement a dereference and a ref methods.
   * References to embedded objects are possible.
   * Arbitrary objects can be saved: They either implement a savedict and 
   to_classdict methods, are represented unchanged if they are of the right
   type (SAME_TYPES) or they are pickled.
   * Container traits are handled correctly.

The drawbacks I can think of are:

* The performance has not been taken into account at all.
* No fancy query meta language (but pymongo is easy enough to use).

Dependencies
------------

* [pymongo](http://api.mongodb.org/python/current/installation.html)
* [IPython](http://ipython.org/)


Install
-------

Download the package and run `python  setup.py install`.


Example
-------

````
import datetime

import mongotraits
from IPython.utils import traitlets

mongotraits.connect('test')
    

class BlogPost(mongotraits.Document):
    author = traitlets.Unicode()
    title = traitlets.Unicode()
    content = traitlets.Unicode()
    references = traitlets.List(mongotraits.Reference(__name__ + '.BlogPost'))
    

my_post = BlogPost(author = 'Zah', title = "First Post", content = "Mongotraits is nice and easy")
other_post = BlogPost(author = 'Zah', title = "Second Post", content = "Another post", references = [my_post,])
my_post.save()
other_post.save()

#The object is already saved in MongoDB
del other_post

#Can find using 
loaded_post= BlogPost.find_one({'title':"Second Post"})

#Same id always corresponds to the same Python object.
assert(loaded_post.references[0] is my_post)
````

Known bugs
----------

Circular references do not work properly at the moment.
