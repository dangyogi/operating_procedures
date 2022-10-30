# hand_off.py

r'''Trying to create some kind of data structure container that is just data in the views,
but can be customized in the template to produce whatever html code the template designer
want.

Looking at BNF, there are:

   - sequences of generally dissimilar things
     - seem like attrs on an object
   - terminals (atoms)
     - seem like tag: data
   - alternates
     - each alt is tag: X
   - optional
     - can be None
   - repeated
     - list

What about key: value pairs?

Then the template designer puts template 
'''
