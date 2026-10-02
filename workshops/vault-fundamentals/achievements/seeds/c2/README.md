# The Right Lease

The app needs database credentials that are valid for 2 minutes, and never for more than 10 minutes in total.

Make a **new** database role called `c2-app` (do not change the lab's `app` role) with those limits, then read
`database/creds/c2-app` once so a credential exists. Use the database connection `app-db` from Lab 12 step 1
(`bao read database/config/app-db` must work; if it doesn't, do that step first).

Work in your own namespace: `export BAO_NAMESPACE=students/$USER`. Then run `dojo-check c2`.
