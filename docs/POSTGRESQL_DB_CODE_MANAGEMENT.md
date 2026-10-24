# PostgreSQL Database Management in VS Code (DBCode)

DBCode is a PostgreSQL extension for VS Code: connect to local Postgres or cloud providers like Neon and Supabase, browse schemas and data, write SQL with schema-aware autocomplete, and edit rows visually without leaving your editor. Install DBCode to get started, or see how it compares to standalone database tools.

## Overview

PostgreSQL is a powerful, open-source relational database management system (RDBMS) with over 30 years of active development. It is known for:

- **Advanced features**: Robust support for JSON, full-text search, and geospatial data
- **Extensibility**: Custom data types, functions, and procedural languages
- **Strong standards compliance**: SQL standard compatibility and ACID compliance
- **Concurrency**: Multi-version concurrency control (MVCC) for high performance
- **Community support**: Large ecosystem of extensions and tools

PostgreSQL is the preferred choice for applications requiring data integrity, complex queries, and handling large datasets, from small projects to enterprise systems.

## Connecting to PostgreSQL in DBCode

1. Open the DBCode Extension: Launch Visual Studio Code and open the DBCode extension.
2. Add a New Connection: Click on the "Add Connection" icon.
3. Complete connection form: Select PostgreSQL as the database type and enter:
   - Host address (default port: 5432)
   - Authentication method and PostgreSQL username
   - Password when using username/password authentication
   - Database name
   - SSL options (if required)
4. Connect: Click save to connect to your PostgreSQL database.
5. Start Managing Your Database: Once connected, explore schemas, tables, and run queries.

For detailed instructions on connecting to PostgreSQL, refer to the Connect article.

### AWS IAM Authentication

On Amazon RDS and Aurora, sign in with an AWS authentication profile instead of a password. DBCode creates and refreshes the IAM token for you.

### Kerberos / GSSAPI Authentication

DBCode can authenticate to compatible PostgreSQL servers with your current operating-system credential. Select Integrated (Kerberos) instead of entering a database password.

- **Windows**: DBCode uses the current signed-in identity through the Kerberos SSP. It does not use Negotiate or fall back to NTLM.
- **macOS and Linux**: Obtain a ticket before connecting, for example with `kinit user@REALM`. DBCode uses the existing ticket cache and does not acquire a ticket for you.
- PostgreSQL still requires a username in its startup message. Enter the database role that your server maps the Kerberos identity to.
- Integrated authentication requires a host/TCP connection. It is not available for Unix sockets.
- DBCode does not accept or manage keytabs. Ticket and service-account setup stays with your operating system and environment administrator.

## Server and Connection Setup

Ask the environment administrator to:

- Configure PostgreSQL `gss` or Windows `sspi` authentication in `pg_hba.conf`
- Register the exact service principal name (SPN) to the PostgreSQL service account
- Map the Kerberos identity to a database role

Configuration details:

- Use the server's DNS hostname in Host.
- On Windows, DBCode uses the `postgres/<host>` SSPI target.
- On macOS and Linux, it passes `postgres@<host>` as the GSS host-based service target, which corresponds to a registered Kerberos service principal such as `postgres/<host>@REALM`.
- Change Kerberos Service Name only when the administrator registered PostgreSQL under another service name.
- Select Integrated (Kerberos) and enter the mapped PostgreSQL username.
- Leave Kerberos Principal empty to use the default ambient credential. On macOS and Linux you can select another principal that already exists in the credential cache. This setting does not run `kinit` or acquire a ticket. Explicit principal selection is not supported on Windows.
- Configure SSL/TLS normally. Kerberos authenticates the user, while TLS encrypts the connection. Full certificate verification also verifies the server certificate chain and hostname; trust-certificate mode does not verify server identity.
- When using an SSH tunnel, keep Host set to the remote PostgreSQL hostname. DBCode routes the TCP connection through the local tunnel while retaining the remote hostname for the SPN and, when full TLS verification is enabled, the certificate hostname check.

DBCode does not expose GSS encrypted transport or `gssencmode`. The native binding cannot verify per-record confidentiality, so use SSL/TLS when the connection must be encrypted.

### Debugger and Client Tools

Integrated authentication is used for ordinary pooled connections and for the PostgreSQL debugger's readiness, target, proxy, and stop/control connections. Each physical connection creates its own Kerberos context and does not reuse a password.

Table DDL, backup, and restore operations run through local PostgreSQL client tools (`pg_dump`, `pg_restore`, and `psql`). For integrated authentication:

- Install PostgreSQL 16 or newer client tools with GSSAPI or SSPI support.
- DBCode disables password prompts and requires a GSSAPI server authentication request, while preserving the connection's TLS verification mode.
- These operations always use the default ambient credential. If the connection selects an explicit principal, clear it before running table DDL, backup, or restore.
- On Windows, the server must use PostgreSQL GSSAPI authentication for these tool operations. DBCode rejects the client tools' server-side SSPI path because it can use Negotiate and NTLM.

### Troubleshooting

| Error or symptom | What to check |
|---|---|
| Kerberos context initialization fails | Confirm the current ticket with `klist`, the realm and DNS configuration, and the exact service SPN. |
| PostgreSQL rejects the mapped role | Check the username, `pg_hba.conf`, `pg_ident.conf`, and the server's identity mapping. |
| Principal selection fails on Windows | Clear Kerberos Principal. Windows uses only the current signed-in identity. |
| Client tools require PostgreSQL 16 or newer | Install newer `pg_dump`, `pg_restore`, and `psql` tools, then retry. |
| Client tools report no GSSAPI or SSPI support | Install a PostgreSQL client build that includes integrated authentication support. |
| TLS hostname verification fails | Connect with the DNS hostname present in the server certificate instead of a local tunnel address or IP alias. |
| Integrated authentication is unavailable | Switch from a socket to a PostgreSQL host/TCP connection and confirm that Integrated (Kerberos) is available in the authentication options. |

### Connect Multiple Databases

A number of cloud providers offer PostgreSQL as a service, including AWS RDS, Azure Database for PostgreSQL, and Google Cloud SQL. To connect to a cloud provider and access multiple databases:

1. Open the DBCode Extension: Launch Visual Studio Code and open the DBCode extension.
2. Add a New Connection: Click on the "Add Connection" icon.
3. Select Your Provider: Choose the cloud provider from the list on the right.
4. Authenticate: Follow the authentication process specific to the provider.
5. Start Managing Your Databases: Explore multiple PostgreSQL instances from a single connection.

For detailed instructions on connecting to PostgreSQL cloud services, refer to the Connect a Cloud Provider article.

### Scheduled Jobs (pg_cron)

When the `pg_cron` extension is installed, DBCode shows its scheduled jobs in a Scheduled Jobs (pg_cron) node under that database, alongside its schemas. Each job row shows its cron schedule and status, with the full details in the tooltip.

- **Enable and disable**: Right-click a job to enable or disable it (`cron.alter_job`, requires `pg_cron` 1.4 or later).
- **Script definitions**: Open a job to view a `cron.schedule` statement that recreates it. Scripting is read-only; change a job with `cron.schedule`/`cron.alter_job` in a query editor.
- **Drop**: Right-click a job to drop it (`cron.unschedule`).

`pg_cron` stores its entire job catalog in a single database per cluster (`cron.database_name`, `postgres` by default) and the extension can only be created there, so the node appears under that one database - expand it to see your scheduled jobs. It is available on managed PostgreSQL that ships `pg_cron`, including AWS RDS/Aurora, Azure Database for PostgreSQL, Google Cloud SQL, and Supabase.

## DBCode Features for PostgreSQL

With DBCode, you can perform these essential tasks when working with PostgreSQL:

- **Schema Browser**: Navigate through databases, schemas, tables, views, and extensions
- **Data Editing**: Edit table data with full support for PostgreSQL data types including JSON/JSONB
- **Stored Procedure Management**: Create and edit functions in SQL, PL/pgSQL, Python, and other languages
- **Bulk Data Import/Export**: Import from CSV, Excel, and JSON files with type conversion
- **Live Streaming**: Subscribe to PostgreSQL LISTEN/NOTIFY channels to receive real-time events in the data grid. Right-click a channel or run `LISTEN channel_name;` in the editor

## Debugging PL/pgSQL Functions and Procedures

DBCode can debug PL/pgSQL functions and procedures with breakpoints, stepping, variables, and watches, using the native VS Code debug UI. Debugging is built on the `pldebugger` plugin, which is maintained alongside PostgreSQL and ships as a standard package on most distributions. Three things have to be in place.

### 1. Load the `plugin_debugger` plugin

The plugin has to be loaded when the server starts, so it must be listed in `shared_preload_libraries`. Install the package for your server version first, for example on Debian or Ubuntu with the PostgreSQL APT repository:

```bash
sudo apt-get install postgresql-17-pldebugger
```

Then add it to `postgresql.conf` and restart the server:

```
shared_preload_libraries = 'plugin_debugger'
```

This setting can only be changed with a restart, and it is server-wide rather than per database. If you already load other libraries, add `plugin_debugger` to the existing comma-separated list rather than replacing it.

On a managed or hosted PostgreSQL service you set the same thing through the provider's parameter settings (a parameter group, flag, or configuration page) instead of editing `postgresql.conf` directly, and apply the restart from the provider's console. Whether a given service exposes `plugin_debugger` and ships the package varies, so check your provider's documentation for the parameter and the available extensions.

To confirm it is loaded:

```sql
SHOW shared_preload_libraries;
```

### 2. Install the `pldbgapi` extension

The plugin exposes its API through an extension, which is created per database. Run this in each database you want to debug in:

```sql
CREATE EXTENSION pldbgapi;
```

When the extension is available on the server but not yet created in the database you are connected to, DBCode offers to install it for you when you start a debug session, so you do not have to run this by hand.

### 3. Connect with a role that can debug

Attaching a debugger to a routine requires the connected role to be a superuser, or the owner of the routine being debugged. This is enforced by PostgreSQL itself rather than by DBCode, and it cannot be granted: a `GRANT` on the routine does not make a role eligible.

Be aware that the elevated roles offered by managed services (such as `rds_superuser`) are not true superusers, so a role holding one still needs to own the routine it is debugging.

### What can be debugged

Only routines written in `LANGUAGE plpgsql` can be debugged, which covers PL/pgSQL functions and procedures. Routines in `sql`, `c`, or another language cannot be stepped through, and DBCode tells you which language it found instead of failing quietly.

### Checking the setup

DBCode checks all three requirements when you start a debug session, so you do not have to work out which piece is missing. When everything passes, the session just starts.

If the `pldbgapi` extension is available on the server but has not been created in the database you are connected to, DBCode offers to create it for you. Accept and the session carries on.

Anything else stops the session with a message naming what is missing and what to do about it, along with a Setup guide button that opens this page.

## DBCode vs. Standalone Database Tools

| Capability | DBCode (VS Code extension) | Standalone database tools (pgAdmin, DBeaver, psql, etc.) |
|---|---|---|
| Editor integration | Runs inside VS Code alongside code | Separate application or terminal |
| Schema browsing | Schema browser in the editor sidebar | Dedicated GUI or `\\d` / information schema queries |
| SQL authoring | Schema-aware autocomplete in the editor | SQL editor or REPL |
| Data editing | Visual row editing with JSON/JSONB support | Grid editor or `UPDATE`/`INSERT` statements |
| Bulk import/export | CSV, Excel, JSON import with type conversion | `COPY`, `\copy`, or tool-specific wizards |
| Real-time events | LISTEN/NOTIFY streaming in the data grid | `LISTEN` in a session; tool-dependent |
| Stored procedures | Create/edit functions in SQL, PL/pgSQL, Python, etc. | SQL editor or GUI |
| Scheduled jobs | pg_cron job enable/disable/drop/tooltip | `cron.schedule`/`cron.alter_job`/`cron.unschedule` SQL |
| Debugging | PL/pgSQL debugging via native VS Code debug UI (`pldebugger`) | `pldbgapi`-based debuggers or `RAISE NOTICE` |
| Cloud providers | Neon, Supabase, AWS RDS, Azure, Google Cloud SQL | Native driver/connection string support |
| Authentication | Password, AWS IAM, Kerberos/GSSAPI, SSL/TLS | Driver-dependent; `pg_hba.conf` governed |
| Client-tool operations | Table DDL, backup, restore via `pg_dump`/`pg_restore`/`psql` | Direct invocation of client tools |

By using PostgreSQL with DBCode, you can streamline your database development workflow within the familiar VS Code environment, making complex database tasks more accessible.

For more information about PostgreSQL, check out PostgreSQL.
