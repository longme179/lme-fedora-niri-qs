"""Resolve bundled provider references; explicit bindings retain narrow capabilities."""
import hashlib
import importlib.util
from pathlib import Path
import sys

from feature_catalog import CatalogError, resource


def provider_factories(catalog, fallbacks, *, root=None):
    root = (Path(root) if root is not None else Path(__file__).resolve().parents[1]).resolve()
    resolved = dict(fallbacks)
    for ident, record in catalog.get('backend', {}).items():
        if ident not in fallbacks: raise CatalogError('Unbound backend feature: '+ident)
        path = resource(root, record['entry'], '.py')
        if path != root/record['entry']: raise CatalogError('Backend entry must be a canonical scripts source')
        module = sys.modules.get(path.stem)
        try:
            if module is None or Path(getattr(module, '__file__', '')).resolve() != path:
                name = '_lme_catalog_provider_'+hashlib.sha256(str(path).encode()).hexdigest()
                module = sys.modules.get(name)
                if module is None:
                    spec = importlib.util.spec_from_file_location(name, path)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[name] = module
                    try: spec.loader.exec_module(module)
                    except BaseException:
                        sys.modules.pop(name, None)
                        raise
            factory = getattr(module, record['factory'])
            if not callable(factory): raise ValueError('Factory is not callable')
        except Exception as error:
            raise CatalogError(f'Backend provider {ident}: {error}') from error
        resolved[ident] = factory
    return resolved
