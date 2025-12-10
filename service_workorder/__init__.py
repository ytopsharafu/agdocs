import sys

__version__ = "2.0"

# Alias the package as `service_workorder.service_workorder` so frappe's module loader works
_module = sys.modules[__name__]
sys.modules.setdefault(__name__ + ".service_workorder", _module)
setattr(_module, "service_workorder", _module)

from . import api
