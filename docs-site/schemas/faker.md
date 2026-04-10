# Faker Integration

The generator supports [Faker](https://faker.readthedocs.io/) providers via the
`faker` hint in `arg.properties`. This gives you access to hundreds of realistic
data generators for names, emails, addresses, phone numbers, and more.

## Installation

Faker is an optional dependency:

```bash
pip install avro-datagen[faker]
```

The generator works without Faker installed -- a `RuntimeError` is raised only
if a schema uses the `faker` hint and the package is missing.

## Simple usage

Pass the Faker method name as a string:

```json
{
  "name": "customerName",
  "type": "string",
  "arg.properties": { "faker": "name" }
}
```

### Common methods

| Method | Example output |
|--------|---------------|
| `name` | "John Smith" |
| `first_name` | "Sarah" |
| `last_name` | "Williams" |
| `email` | "j.doe@example.com" |
| `phone_number` | "+1-555-123-4567" |
| `address` | "123 Main St, Springfield" |
| `city` | "Cape Town" |
| `country` | "South Africa" |
| `company` | "Acme Corp" |
| `job` | "Software Engineer" |
| `url` | "https://example.com" |
| `iban` | "DE89370400440532013000" |
| `credit_card_number` | "4111111111111111" |
| `date_of_birth` | "1985-03-12" |
| `text` | "Lorem ipsum..." |
| `sentence` | "The quick brown fox." |
| `uuid4` | "a1b2c3d4-..." |
| `currency_code` | "ZAR" |
| `color_name` | "teal" |
| `user_agent` | "Mozilla/5.0..." |
| `ipv4` | "192.168.1.1" |
| `mac_address` | "00:1B:44:11:3A:B7" |

See the full list at [Faker Providers](https://faker.readthedocs.io/en/master/providers.html).

## Advanced usage

Pass a dict with `method`, `args`, `kwargs`, and/or `locale`:

### With arguments

```json
{
  "name": "accountNumber",
  "type": "string",
  "arg.properties": {
    "faker": { "method": "bothify", "args": ["###-???-####"] }
  }
}
```

### With keyword arguments

```json
{
  "name": "age",
  "type": "int",
  "arg.properties": {
    "faker": { "method": "random_int", "kwargs": { "min": 18, "max": 85 } }
  }
}
```

### With locale

Generate locale-specific data:

```json
{
  "name": "customerName",
  "type": "string",
  "arg.properties": {
    "faker": { "method": "name", "locale": "af_ZA" }
  }
}
```

```json
{
  "name": "japaneseAddress",
  "type": "string",
  "arg.properties": {
    "faker": { "method": "address", "locale": "ja_JP" }
  }
}
```

## Combining with rules

Use Faker inside conditional rules:

```json
"arg.properties": {
  "rules": [
    {
      "when": { "field": "country", "equals": "ZA" },
      "then": { "faker": { "method": "name", "locale": "af_ZA" } }
    },
    {
      "when": { "field": "country", "equals": "JP" },
      "then": { "faker": { "method": "name", "locale": "ja_JP" } }
    }
  ]
}
```

!!! note "Seed behaviour"
    Faker has its own RNG. When using `--seed`, Faker-generated values are
    **not** controlled by the generator's seed. For fully deterministic output,
    prefer the built-in hints (`options`, `pattern`, `pool`).
