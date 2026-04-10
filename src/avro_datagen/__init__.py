"""Schema-driven data generator for Avro schemas with arg.properties hints."""

from avro_datagen.generator import generate
from avro_datagen.resolver import RecordResolver, load_schema

__all__ = ["RecordResolver", "generate", "load_schema"]
