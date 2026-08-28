FROM pgvector/pgvector:pg15

# Set build-time variables or labels
LABEL maintainer="CampusFlow AI Team"
LABEL version="1.0"
LABEL description="PostgreSQL database container for CampusFlow AI system"

# The official image already runs scripts in /docker-entrypoint-initdb.d/ in alphabetical order.
# We will place init.sql, schema.sql, and seed.sql there, but we will make init.sql execute first
# and orchestrate the execution or let Postgres execute them alphabetically.
# Since postgres executes scripts in alphabetical order:
# 1. 01-schema.sql
# 2. 02-seed.sql
# We can name our files or write a simple script that coordinates them.
# The user specified:
# docker-entrypoint-initdb.d/
#   ├── schema.sql
#   ├── seed.sql
#   └── init.sql
# If postgres runs alphabetical order, we can make init.sql execute first or use init.sql to \i schema.sql and \i seed.sql.
# Let's verify that init.sql runs schema.sql and seed.sql using \i or \ir to keep it clean,
# and copy them into the docker image.

# Copy the initialization scripts to docker-entrypoint-initdb.d
COPY docker-entrypoint-initdb.d/ /docker-entrypoint-initdb.d/

# Ensure scripts have correct execution permissions
RUN chmod +x /docker-entrypoint-initdb.d/*.sql
