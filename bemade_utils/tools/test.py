import importlib
from functools import wraps


def patch_test(original_method):
    """
    A decorator that patches an Odoo test method with a new one.
    The original_method is a direct reference to the method to be patched.
    """
    def decorator(new_method):
        @wraps(new_method)
        def wrapper(*args, **kwargs):
            return new_method(*args, **kwargs)

        # Extract module and class names
        module_name = original_method.__module__
        class_name = original_method.__qualname__.split('.')[0]

        # Import the module
        module = importlib.import_module(module_name)
        # Get the class
        cls = getattr(module, class_name)

        # Replace the original method with the new one
        setattr(cls, original_method.__name__, wrapper)

        return wrapper
    return decorator
