# Schemas for `digest` input files

## Overview
`digest` supports TSV files as inputs. 
Expected columns in a digest file are defined in JSON files called digest schemas.
There are different schemas for digest files containing different modalities of data (e.g. imaging vs. phenotypic).

| Schema | Modality of data in corresponding digest file |
| ----- | ----- |
| `imaging_digest_schema.json` | Processing pipeline output and derivative availability |
| `phenotypic_digest_schema.json` | Demographic and phenotypic assessment data |

## How to read the schema
### Column categories
Within a schema, columns are grouped into two semantic categories. These categories are purely for organizational purposes and do not appear in a digest file.

**Global columns:** Columns describing basic metadata that should have the same meaning regardless of the specific event described by a given record 
(e.g., a certain processing pipeline or phenotypic assessment), and do not depend on event outputs.

**Event-specific columns:** Columns whose values may have event-specific meanings.
e.g., in the schema for an imaging digest, the `"PIPELINE_STATUS_COLUMNS"` convey info about processing pipeline completion that depends on pipeline-specific outputs and may have varying values depending on the pipeline tracker used.

### Column attributes
Recognized columns are described in the schema using the following attributes:
- `Description`
  - Describes the column contents, along with the meaning of different acceptable values for categorical columns.
- `dtype`
  - The expected type for values in the column.
- `IsRequired`
  - Whether or not the column is required to be present in the digest file. 
  If `true`, the dashboard will throw an error if the column is missing.
- `Range`
  - Acceptable values for data in the column. 
  Only present for categorical columns.
