Mongotraits
===========

A liteweight simple Object Document Manager to connect python objects to MongoDB.

Features
--------

   * Fields are IPython TraitTypes with the metadata db=True.
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
