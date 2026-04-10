# Schema Examples

## Minimal record

```json
{
  "type": "record",
  "name": "Event",
  "fields": [
    { "name": "id", "type": { "type": "string", "logicalType": "uuid" } },
    { "name": "message", "type": "string" },
    { "name": "timestamp", "type": { "type": "long", "logicalType": "timestamp-millis" } }
  ]
}
```

## Transaction (full-featured)

This schema demonstrates most features: options with weighting, conditional
rules, templates, refs, pools, timestamp ranges, and union types.

```json
{
  "type": "record",
  "name": "Transaction",
  "namespace": "txn.raw.v1",
  "fields": [
    {
      "name": "correlationId",
      "type": { "type": "string", "logicalType": "uuid" }
    },
    {
      "name": "sourceId",
      "type": "string",
      "arg.properties": {
        "options": ["bank-api", "card-processor", "mobile-app"]
      }
    },
    {
      "name": "customerId",
      "type": { "type": "string", "logicalType": "uuid" },
      "arg.properties": { "pool": 50 }
    },
    {
      "name": "category",
      "type": "string",
      "arg.properties": {
        "options": [
          "GROCERIES", "GROCERIES",
          "TRANSPORT", "TRANSPORT",
          "DINING", "DINING",
          "UTILITIES",
          "ENTERTAINMENT",
          "HEALTHCARE",
          "RETAIL", "RETAIL"
        ]
      }
    },
    {
      "name": "merchantName",
      "type": "string",
      "arg.properties": {
        "rules": [
          {
            "when": { "field": "category", "equals": "GROCERIES" },
            "then": { "options": ["Pick n Pay", "Checkers", "Woolworths Food", "Spar"] }
          },
          {
            "when": { "field": "category", "equals": "TRANSPORT" },
            "then": { "options": ["Uber SA", "Bolt", "Gautrain", "Shell", "Engen"] }
          }
        ]
      }
    },
    {
      "name": "amount",
      "type": "double",
      "arg.properties": {
        "rules": [
          {
            "when": { "field": "category", "equals": "GROCERIES" },
            "then": { "range": { "min": 35.0, "max": 4500.0 } }
          },
          {
            "when": { "field": "category", "equals": "TRANSPORT" },
            "then": { "range": { "min": 15.0, "max": 2500.0 } }
          }
        ]
      }
    },
    {
      "name": "currency",
      "type": "string",
      "default": "ZAR"
    },
    {
      "name": "description",
      "type": "string",
      "arg.properties": {
        "template": "Purchase at {merchantName}"
      }
    },
    {
      "name": "timestamp",
      "type": { "type": "long", "logicalType": "timestamp-millis" },
      "arg.properties": { "range": { "min": "-30d", "max": "now" } }
    },
    {
      "name": "createdAt",
      "type": { "type": "string", "logicalType": "iso-timestamp" },
      "arg.properties": { "ref": "timestamp" }
    }
  ]
}
```

## With Faker fields

```json
{
  "type": "record",
  "name": "Customer",
  "fields": [
    {
      "name": "id",
      "type": { "type": "string", "logicalType": "uuid" }
    },
    {
      "name": "name",
      "type": "string",
      "arg.properties": { "faker": "name" }
    },
    {
      "name": "email",
      "type": "string",
      "arg.properties": { "faker": "email" }
    },
    {
      "name": "phone",
      "type": "string",
      "arg.properties": { "faker": "phone_number" }
    },
    {
      "name": "company",
      "type": "string",
      "arg.properties": { "faker": "company" }
    },
    {
      "name": "address",
      "type": "string",
      "arg.properties": {
        "faker": { "method": "address", "locale": "af_ZA" }
      }
    }
  ]
}
```

## Pattern-based IDs

```json
{
  "type": "record",
  "name": "Order",
  "fields": [
    {
      "name": "orderId",
      "type": "string",
      "arg.properties": { "pattern": "ORD-[A-Z]{2}-[0-9]{6}" }
    },
    {
      "name": "sku",
      "type": "string",
      "arg.properties": { "pattern": "[A-Z]{3}-[0-9]{4}" }
    }
  ]
}
```
