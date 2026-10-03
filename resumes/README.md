# Local resume files

Place verified PDF copies here manually. PDFs are ignored by Git. Nothing is
automatically downloaded from Google Drive.

After adding e.g. `resumes/technical.pdf`, use `PATCH /resumes/{id}` with
`{"local_path":"resumes/technical.pdf"}`. The path must resolve to an existing PDF
inside this directory. `GET /resumes` exposes profile metadata, not file contents.
