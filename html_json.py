"""Serialize untrusted source strings as JSON inside an HTML script element."""
import json


def dumps(value, **options):
    # HTML parses </script> before JSON, even for application/ld+json. Preserve
    # the original JSON value while preventing any HTML script-boundary breakout.
    return (json.dumps(value, **options)
            .replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026'))
