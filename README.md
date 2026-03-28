# 234 Seats

A simple website for predicting election results and ranking users based on their accuracy or other metrics. Developed for the Tamil Nadu legislative assembly elections in April-May 2026, hence the name 234 seats.

This is a personal project for educational purposes.

## Feature Wishlist

- Home page shows a map of all the constituencies, a subset of which are clickable, and a table of users and overall metrics
    - clicking on a constituency takes you to the constituency page
    - links to Harsh’s blogs and analysis of the election overall
- The overall metrics table: 
    - table of users with columns: num predictions, correct seats so far, deviation in vote share (max, MAE, RMSE), 
    - Can sort by any column
- Constituency page:
    - Details: name, district, population, current MLA and party
    - A short writeup explaining the history and current context of the fight for this seat
    - User form to submit predictions (winner from dropdown, vote share % of winner, text prediction/comment for that seat)
    - After submission, can see a predictions table on this seat: each user’s predicted winner, vote share, comments
    - Can only see others’ predictions once you’ve submitted yours
    - After election results are out, the prediction table also has the actual winner and vote share
    - Stretch: Edit submission later?
- Managing the website:
    - To start with, many of these things can be hardcoded in the repo / edited manually using some utility scripts -- they don't need a web interface
    - Admin selects a set of seats that are open to predictions, and publish writeup for each, past X results
    - Register users?
        - Start with: admin makes usernames and passwords and sends to our group
    - Results:
        - Admin can enter final results manually
        - Stretch goal: periodically scrape live results from ECI and update winners-so-far
        - Stretch: graph of standings over time
- Stretch: Export results, predictions as CSV/spreadsheet
- Stretch: labels/badges/titles for each user based on wins / other honorable mentions
- After elections: add functionality to archive this election and use website again for a new one. This means the architecture of the website / database should be designed so that everything is tied to a particular election, so that it can be reused for the next election.
