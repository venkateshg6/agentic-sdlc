# References and provenance

Original implementation prepared with AI assistance for this assignment. No
third-party repository was forked or copied into this project. Standard-library
APIs and container isolation patterns were informed by primary documentation:

- Python sqlite3: https://docs.python.org/3/library/sqlite3.html
- Python unittest: https://docs.python.org/3/library/unittest.html
- Python WSGI reference server: https://docs.python.org/3/library/wsgiref.html
- Docker resource constraints: https://docs.docker.com/engine/containers/resource_constraints/
- Groq compatible HTTP API: https://console.groq.com/docs/openai

Live API compatibility can differ by model/provider. The adapter intentionally
uses the common chat-completions subset and validates JSON locally. Model IDs,
free tiers and performance are not hardcoded assumptions.

The company assignment and emails are not included or published. Obtain permission
before publishing company-labelled material. Third-party runtime/container images
retain their own licenses. Add your preferred license only after deciding the
appropriate distribution terms for the submission; no ownership claim about
company material is made here.
