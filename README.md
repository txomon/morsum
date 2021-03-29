# Misc test

## Data Warehouse and Mysql syncing

**Bob has data being ingested into a data warehouse (e.g BigQuery but can be something
else). However, Jill wants to access the data from Mysql in order to serve some APIs.
Through discussions, they decided the best approach would be to sync some tables in Mysql
to tables in the data warehouse. Please come up with an approach to sync between data
warehouse and Mysql. This should include:**

* **The basic idea to sync them together**

  There are different ways to sync data depending on how the data is structured and what
  the sync requirements are. I'm going to explain two cases.

  Solution 1:
    * GBQ tables are ingestion time partitioned (Eg. Event log in an event-sourcing
      architecture) or small enough
    * The data only flows from GBQ to MySQL

  In a required_time ETL, export each modified partition to file, and load them in the
  MySQL db inside a transaction. For idempotency purposes, a `DELETE FROM` can be issued
  for all data from a given partition. Making sure that the partition field is available
  in the data (maybe as a new column), and inserting it in mysql in a partitioned table.

  The amount of data to be synced shouldn't be too big, or it will make the MySQL
  Database have performance issues.

  Solution 2:
    * GBQ tables are not partitioned (Eg. A materialised event stream in event-sourcing
      architecture)
    * The data only flows from GBQ to MySQL
    * The data is too big to sync as a whole using Solution 1 (10GB+ rows)

  Write a streaming application that collects (or computes in worst case) changes to each
  of the rows and then issues updates, inserts or deletions to the MySQL DB. The use of
  this method is highly discouraged and is probably the wrong solution (for example,
  materialising the data directly on MySQL through streaming would be better than trying
  to infer the inserts/updates/deletes from the table itself). Hashing of whole rows can
  be applied to generate optimized upsert statements and deletions.

* A diagram on how the data flows, gets inserted, updated, deleted

  Solution 1:
  ```text
  ┌──────────┐     ┌─────┐      ┌────────────┐     ┌───────┐
  │          │     │     │      │            │     │       │
  │ BigQuery ├────►│ GCS ├─────►│ Python App ├────►│ MySQL │
  │          │     │     │      │            │     │       │
  └──────────┘     └─────┘      └────────────┘     └───────┘
  ```

  Solution 2:
  ```text
  ┌──────────┐     ┌────────────┐     ┌───────┐
  │          │     │            │     │       │
  │ BigQuery ├────►│ Python App ├────►│ MySQL │
  │          │     │            │     │       │
  └──────────┘     └────────────┘     └───────┘
  ```

* What happens if there is an isolated table

  Not sure what the definition of an isolated table is, but supposing it means having a
  table in MySQL that is not Bigquery synced, it wouldn't affect the solutions.

* What happens when there are linked tables such as recipes, ingredients and
  relationships.

  Relationships don't exist in GBQ, and data would be eventually consistent. If the
  original data is ingestion-time partitioned and follows an append-only design, then the
  data is likely to be consistent within a partition. By complicating the sync process (
  by having it awareness of inter-table dependencies), it should be possible to load all
  tables within one transaction.

* What is the predicted latency between data warehouse and Mysql and how can Bob reduce
  that?

  Solution 1 can go down to around a minute of latency, depending on MySQL load
  performance, and the amount of data. If using ingestion time partitioning which
  supports hourly partitions to reduce the amount of partitions to sync, could lower the
  amount of data to sync.

  Solution 2 can go down to a few seconds in latency, however materialising the table
  directly in MySQL would be rather recommended.

* How can it be monitored that processes work fine and the data is in sync?

  In Solution 1 the addition of a last-sync timestamp would allow to compute deltas from
  the given timestamp recovering from missed syncs in Solution 1 transparently.

  Solution 2 would require full app monitoring and error tolerance for undelivered MySQL
  statements, again, materialising the table directly in MySQL would be a better option.

* If for some reason data desyncs, how can Bob resync it?

  Solution 1 would transparently sync all deltas with the last-sync timestamp addition.

  Solution 2 would require a full data export import if there is no retry logic for
  failing to deliver MySQL statements.

## API

**Using python and Flask construct a REST API about recipes. Create a few tables in a
mysql database that has recipe information and recipe ingredients. Create an API to**

- **get, edit, delete and create recipes.**
- **get recipes by certain ingredient_id**

**Good python techniques should be used, especially regarding the design of the API.
Furthermore, some error handling is also expected. Code should be added to a git
repository - this repo can be shared with us once the tasks are done.**

I have implemented the things fast, only tested happy path. I have set up:

* Flask
* SqlAlchemy
* Marshmallow
* Pytest

I would like to remove flask-sqlalchemy because it doesn't bring much to the table
but couples the view and the db together, but meh. It has taken me 2:30h, and although
there are improvements that could be done (such as exposing more than the IDs etc.).
But for a technical test I believe it's sufficient.
