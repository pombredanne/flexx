""" This tests the Model class.
"""

from flexx.util.testing import run_tests_if_main, raises

import logging
import tornado

from flexx.app.model import Model, _get_active_models
from flexx import event, app

class Foo1(Model):
    
    @event.prop
    def title(self, v=''):
        return v
    
    class JS:
        
        @event.prop
        def blue(self, v=0):
            return v

class Foo2(Foo1):
    
    class JS:
        
        @event.prop
        def red(self, v=0):
            return v


class Foo3(Foo2):
    py_attr = 42
    
    @event.prop
    def js_attr(self, v=0):
        return v
    
    class JS:
        js_attr = 42
        
        @event.prop
        def py_attr(self, v=0):
            return v

class Foo4(Foo3):
    
    @event.prop
    def title(self, v=''):
        return v + 'x'
    
    class JS:
        
        @event.prop
        def red(self, v=0):
            return v+1

class Foo5(Foo4):
    
    class Both:
        
        @event.prop
        def red(self, v=0):
            return v+1
        
        @event.prop
        def blue(self, v=0):
            return v+1
        
        @event.prop
        def purple(self, v=0):
            return v+1


class Foo6(Foo1):
    
    class JS:
        
        @event.emitter
        def my_awesome_event(self, x):
            """ docs on awesome event. """
            return {}


def test_pairing1():
    
    assert isinstance(Foo1.title, event._emitters.Property)
    assert not hasattr(Foo1, 'blue')
    
    assert not hasattr(Foo1.JS, 'title')
    assert isinstance(Foo1.JS.blue, event._emitters.Property)


def test_no_clashes():
    
    # Attributes that already exist are not overwritten
    assert Foo3.py_attr == 42
    assert Foo3.JS.js_attr == 42
    
    assert isinstance(Foo3.js_attr, event._emitters.Property)
    assert isinstance(Foo3.JS.py_attr, event._emitters.Property)
    
    # Double check in subclass
    assert Foo4.py_attr == 42
    assert Foo4.JS.js_attr == 42
    
    assert isinstance(Foo4.js_attr, event._emitters.Property)
    assert isinstance(Foo4.JS.py_attr, event._emitters.Property)


def test_overloading():
    
    assert Foo2.title is Foo1.title
    assert Foo3.JS.red is Foo2.JS.red
    
    assert Foo4.title is not Foo1.title
    assert Foo4.JS.red is not Foo2.JS.red


def test_both():
    # New prop
    assert Foo5.purple is Foo5.JS.purple
    # Overloaded existing props
    assert Foo5.red is Foo5.JS.red
    assert Foo5.blue is Foo5.JS.blue
    
    # But this fails
    
    with raises(TypeError):
        
        class Foo5_wrong1(Foo4):
            
            @event.prop
            def purple(self, v=0):
                return v+1
            
            class Both:
                
                @event.prop
                def purple(self, v=0):
                    return v+1
    
    with raises(TypeError):
        
        class Foo5_wrong2(Foo4):
            
            class JS:
                @event.prop
                def purple(self, v=0):
                    return v+1
            
            class Both:
                
                @event.prop
                def purple(self, v=0):
                    return v+1


def test_emitters_in_JS():
    # Emitters in JS get a dummy emitter in Py
    assert Foo6.my_awesome_event
    assert 'docs on awesome' in Foo6.my_awesome_event.__doc__
    

    with raises(RuntimeError):
        Foo6.my_awesome_event._func(None)


def test_no_duplicate_code():
    assert '.blue.' in Foo1.JS.CODE
    assert '.blue.' not in Foo2.JS.CODE
    assert '.blue.' not in Foo4.JS.CODE
    
    assert '.red.' not in Foo1.JS.CODE
    assert '.red.' in Foo2.JS.CODE
    assert '.red.' in Foo4.JS.CODE


def test_get_instance_by_id():
    
    # This test needs a default session
    session = app.manager.get_default_session()
    if session is None:
        app.manager.create_default_session()
    
    m1 = Foo1()
    m2 = Foo1()
    
    assert m1 is not m2
    assert app.get_instance_by_id(m1.id) is m1
    assert app.get_instance_by_id(m2.id) is m2
    assert app.get_instance_by_id('blaaaa') is None


def test_active_models():
    
    ioloop = app.create_server(port=0, new_loop=True).loop
    
    # This test needs a default session
    session = app.manager.get_default_session()
    if session is None:
        app.manager.create_default_session()
    
    # Test that by default there are no active models
    m = Model()
    assert not _get_active_models()
    
    # Test that model is active in its context
    with m:
        assert _get_active_models() == [m]
    
    # Can do this
    ioloop.run_sync(lambda x=None: None)
    
    
    class PMHandler(logging.Handler):
        def emit(self, record):
            if record.exc_info:
                self.last_type, self.last_value, self.last_traceback = record.exc_info
            return record
    
    handler = PMHandler()
    app.logger.addHandler(handler)
    
    # Test that we prevent going back to Tornado in context
    handler.last_type = None
    with m:
        assert _get_active_models() == [m]
        # This raises error, but gets caught by Tornado
        ioloop.run_sync(lambda x=None: None)
    assert handler.last_type is RuntimeError
    assert 'risk on race conditions' in str(handler.last_value)


class EmitInInit(app.Model):
    
    def init(self):
        self.res1 = []
        self.res2 = []
        self.emit('foo')
        self.emit('foo')
    
    @event.prop
    def bar(self, v=1):
        return v
    
    @event.connect('foo')
    def on_foo(self, *events):
        self.res1.append(len(events))
    
    @event.connect('bar')
    def on_bar(self, *events):
        self.res2.append(len(events))

def test_can_emit_in_init():
    m = EmitInInit()
    m.on_foo.handle_now()
    m.on_bar.handle_now()
    
    assert m.res1 == [2]
    assert m.res2 == [1]

run_tests_if_main()
