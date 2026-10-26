# NFL Stats

A personal NFL stats app for all 32 teams. It runs as a website that you can add to your
iPhone home screen, where it opens like a regular app. Everything is free: the data
(nflverse), the scheduled updates (GitHub Actions) and the hosting (GitHub Pages).

## How it fits together

```
nflverse (free data on GitHub)
      │  every 6 hours
      ▼
pipeline/build_data.py   ← adds up team stats, ranks all 32 teams
pipeline/players.py      ← player stats (ranked within his position) + rosters
pipeline/context.py      ← opponent strength + injuries (for ratings)
pipeline/ratings.py      ← 0-100 ratings, using config/ratings.json
      │  writes
      ▼
public/data/             ← small files the app reads:
                            teams/<TEAM>.json   (stats, schedule, roster)
                            players/<id>.json   (one per player)
      │
      ▼
Expo app (src/app/)      ← the screens: Teams › Team › Offense/Defense/ST › Category
      │  `npm run build:web`
      ▼
dist/  →  GitHub Pages   ← the live website
```

The `.github/workflows/update-and-deploy.yml` file is the scheduled job. It checks for
new data every 6 hours. If games were played, it saves the new stats and republishes
the site. Otherwise it stops early.

## Folders

| Path | What's in it |
| --- | --- |
| `pipeline/build_data.py` | Downloads nflverse data and calculates team stats |
| `pipeline/players.py` | Player pages (stats by position) and depth-chart-ordered rosters |
| `config/ratings.json` | **Every rating weight, in one place**, with the reasoning written next to each |
| `pipeline/ratings.py`, `pipeline/context.py` | The rating math, opponent strength and injury adjustments |
| `pipeline/boxscore.py` | Box scores for played games: team and player stats, each with the league average and a percentile for the colors |
| `pipeline/averages.py` | League averages shown under every rating (teams vs. all 32 teams; players vs. their position, plus a starters-only average) |
| `public/data/` | The generated stats (one file per team + a team list) |
| `src/app/` | The screens. Each file is a page; the folder names become the web address |
| `src/components/` | Reusable building blocks (stat row, leaders list, team banner) |
| `src/lib/` | Data loading, colors, and the list of teams and categories |
| `scripts/` | Small helpers (app icon drawing, GitHub Pages fixes) |

## Everyday commands

Run these in Terminal from this folder. The first line makes the `node`/`npm`
commands available, and new Terminal windows do this automatically.

```bash
export PATH="$HOME/.local/node/bin:$PATH"
```

```bash
npm run data        # refresh stats from nflverse
```

```bash
npm run web         # open the app in your browser at http://localhost:8081
```

```bash
npm run build:web   # build the website into dist/
```

## Stat notes

- Regular season only for now. Ranks are 1 to 32, where 1 is best. Green means top 10,
  amber means middle, red means bottom 10.
- Stats with ⓘ have a plain-language explanation. Tap the row to see it.
- Players are ranked only against players at the same position (QBs vs QBs, and so on).
  To be ranked in a category, a player needs enough playing time, based on the NFL's own
  leaderboard minimums (for example, 14 pass attempts per team game for QBs). Below that,
  the page still shows his numbers and the position average, and says what he needs.
- Rosters show the 53-man roster plus injured reserve (marked IR), in depth chart order.
  Practice squad players aren't listed.
- "EPA" (Expected Points Added) is nflverse's measure of how much each play helped
  or hurt a team's chances of scoring.

## Ratings (start from Madden, move with real results)

Every team, unit, category, stat, player and player category has a 0-100 rating.

- **Starting point:** each player's Madden NFL 27 launch rating. Team baselines are the
  average Madden rating of their expected starters (QB counts 4×), scaled to Madden's team
  range. Players missing from Madden start at a typical backup rating ("estimated").
- **Madden data:** download the free spreadsheet of EA's launch ratings from
  MaddenRatings.net (Madden NFL 27 page) and save it in `data/madden/`. Running
  `npm run data` then writes `data/madden/madden_overall.csv` (NFL id + overall only), which
  is what the online job uses. The full spreadsheet is never uploaded (it's in `.gitignore`).
- **Learning (pipeline/learn.py):** for each position and team unit, 2025 full-season stats
  plus 2026 stats so far are compared with Madden ratings to learn which stats matter
  (blended 50/50 with the football-knowledge weights in `config/ratings.json`). The fit
  quality for each position is saved in `public/data/ratings_model.json`.
- **Adjusting:** rating = Madden + (stats vs. what that Madden rating normally produces) ×
  how much he's played × how well stats explain Madden at his position. Low-sample players
  stay near Madden and are marked **LTD**.
- **Sliders (Settings ⚙):** stats influence, plus the blend of this season's stats,
  opponent strength, injuries, betting market (teams only), and recent form.
- **Why this rating:** tap any colored rating to see the Madden baseline and how much each
  factor moved it.

## Games and win probability

Tap any game on a team's Schedule to open it. Both teams appear side by side (the same
screen as Compare), with the chance to win at the top. For finished games it shows the
final score and what the model gave each team before kickoff.

- **How it works (pipeline/winprob.py):** each factor is turned into points on the
  scoreboard: home field, Offense/Defense/Special Teams rating gaps, recent form, record
  adjusted for opponents, last season (fading out), and that week's injuries (a starting
  QB is worth about 5.5 points, more for a star). The expected margin becomes a percentage.
- **Only pre-game information is used:** ratings are rebuilt from earlier games, so past
  games are judged fairly.
- **Settings:** every weight is in `config/winprob.json`, with the reasoning next to each.
- **Testing:** each run re-tests the model on every 2025 and 2026 game (each week predicted
  by a model that never saw that week's results) and saves accuracy and calibration to
  `public/data/winprob_report.json`, next to two benchmarks: always picking the home team,
  and the betting favorite.

## Schedule and Power Rankings

The home screen has three tabs: **Schedule**, **Rankings** and **Compare**.

- **Schedule:** every game of a week, grouped by day, with records, kickoff (Mountain Time, Utah) and
  win chances. Arrows or week numbers switch weeks; tapping a game opens the game screen.
- **Power Rankings:** League (all 32 teams), Team units (Offense, Offensive Line, Secondary,
  ...), and Players by position. Tap any row to see why it's ranked there.
- **League power score (pipeline/rankings.py + src/lib/powerRankings.ts):** wins and losses
  in context (each game vs. what an average team would do against that opponent, home or
  away, with that opponent's injuries; close games count as partial results; margins capped
  at 21), the team rating minus key players out now, and recent form. Weights in
  `config/rankings.json`, with sliders in Settings. Byes never lower a team's score.

## Betting market (the "analyst opinion" factor)

There's no free, structured source of analyst opinion, so the betting market stands in for
it (pipeline/market.py). From this season's point spreads and over/under totals (recent
weeks count most), each team gets a market-view rating for offense, defense and overall,
blended in with the "Betting market" slider. In win probability, games with a betting line
use 75% line and 25% model: testing showed the line alone is slightly more accurate, but
this blend is almost as good and keeps the model's factors meaningful.
