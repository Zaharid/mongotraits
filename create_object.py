# -*- coding: utf-8 -*-
"""
Created on Mon Apr  7 21:30:47 2014

@author: zah
"""
from collections import defaultdict

from IPython.utils import traitlets
from IPython.html import widgets

widget_mapping = defaultdict(lambda: widgets.TextWidget, {
     traitlets.Unicode: widgets.TextWidget,
     traitlets.Bool: widgets.CheckboxWidget,
     traitlets.Int: widgets.IntTextWidget,
     traitlets.Float: widgets.FloatTextWidget,
    'Object': EvaluableWidget,

})

#TODO: split
def trait_to_widget(trait_name, trait, obj):
    if hasattr(trait, 'widget'):
        return trait.widget(trait_name, obj)



#TODO:
class DocumentDisplay(object):
    pass

class CreateObjectWindow(object):
    instance = None

    def __init__(self, document):
        """Public constructor."""

        self.closed = False
        self.document = document

        self._popout = widgets.PopupWidget()
        self._popout.description = "Create %s" % self.document.__name__
        self._popout.button_text = self._popout.description

        self._modal_body = widgets.ContainerWidget()
        self._modal_body.set_css('overflow-y', 'scroll')


        self._popout.children = [
            self._modal_body,
        ]
        self.fill()

    def fill(self):
        children = [make_widget(trait) for trait in self.document.traits()]
        self._modal_body.children = children


    def close(self):
        """Close and remove hooks."""
        if not self.closed:
            self._popout.close()
            self.closed = True

    def _fill(self):
        """Fill self with variable information."""
        values = self.namespace.who_ls()
        self._modal_body_label.value = '<table class="table table-bordered table-striped"><tr><th>Name</th><th>Type</th><th>Value</th></tr><tr><td>' + \
            '</td></tr><tr><td>'.join(['{0}</td><td>{1}</td><td>{2}'.format(v, type(eval(v)).__name__, str(eval(v))) for v in values]) + \
            '</td></tr></table>'

    def _ipython_display_(self):
        """Called when display() or pyout is used to display the Variable
        Inspector."""
        self._popout._ipython_display_()
        self._popout.add_class('vbox')
        self._modal_body.add_class('box-flex1')

def create(document):
    return CreateObjectWindow(document)