# cnc-reddit-study

A small, personal, non-commercial learning project. It reads public Reddit posts and comments about consumer desktop CNC machines, using one brand (Makera: Carvera, Carvera Air, Z1) as a case study, to understand which problems new users run into and how hobbyist communities help them.

## What it does

- Uses the official Reddit Data API with an **application-only OAuth token and read access only**.
- Searches public posts in these subreddits: r/Makera, r/CarveraAir, r/hobbycnc, r/CNC, r/Machinists, r/CNCmachining (keywords: `makera`, `carvera`, `z1`), and reads the comment trees of matching threads.
- Waits at least 1 second between requests (at most 60 requests per minute) and backs off when the rate-limit headers run low.

## What it does not do

- No posting, commenting, voting, messaging or moderation. The script has no write calls.
- No private, quarantined or deleted content.
- No profiling: it does not infer sensitive characteristics, re-identify users or match data with off-platform identifiers.
- No AI or machine-learning model training on the data.

## Data handling

- Stored fields: item ID, subreddit, timestamp, title/text, score, comment count, thread ID. **Usernames are not stored**; only a flag marks posts from the brand's official accounts.
- Data stays in a local SQLite file (`data/`, excluded from git). It is not sold, licensed, shared or published in raw form; any write-up uses aggregate findings with links to public threads.
- `python3 reddit_reader.py refresh` re-queries every stored item and drops anything deleted or removed on Reddit.
- The whole dataset is deleted after the date set in `DELETE_AFTER` (within 6 months), or at any time with `python3 reddit_reader.py purge`.

## Setup

Requires Python 3.9+ and an approved Reddit API application. Credentials are read from environment variables or the macOS Keychain and are never stored in this repository:

```bash
security add-generic-password -a "$USER" -s reddit_client_id -w
security add-generic-password -a "$USER" -s reddit_client_secret -w
security add-generic-password -a "$USER" -s reddit_username -w
```

Then:

```bash
python3 reddit_reader.py collect
```

## Policy

This project follows Reddit's Responsible Builder Policy, Data API Terms and Public Content Policy. No Reddit data is collected through the API before access is approved.
