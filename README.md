# Fork of the VALK Streamlit Dashboard for CIU

![CIU Logo](assets/CIU.png)

## Project Description

This dashboard is designed for the analysis and visualization of activities related to the East India Company (EIC) in Elite Dangerous. It provides various pages for analyzing leaderboards, CZ activities (Space & Ground), table views, and more.
It can be easily adapted to other factions or groups by changing the API endpoint and adjusting the filters accordingly.

## Features

- **Leaderboard:** Overview and filtering of commander activities by period and type.
- **CZ Summary:** Evaluation of Space and Ground Combat Zones, including distribution by system, Cmdr, and CZ type.
- **Table View:** Filtered display of all relevant data.
- **Interactive Filters:** Period, system, Cmdr, and more.
- **AgGrid Tables:** Convenient and dynamic table display.
- **API Integration:** Automatic data retrieval via configurable API endpoints.

## Installation

1. **Clone the repository**
   ```bash
   git clone <REPO_URL>
   cd VALKStreamlitDashboard
   ```

2. **Create and activate a Python environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate   # or .venv\Scripts\activate on Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

1. **Create the .env file**

   Copy the `.env_template` file to `.env` and adjust the values:

   ```env
   API_KEY=your_api_key_here_same_as_flask_api
   API_VERSION=1.6.0
   API_BASE=url_of_the_flask_app/api/
   ```

2. **Start the dashboard**
   ```bash
   streamlit run app.py
   ```

## Notes

- API credentials and endpoints are managed centrally via the `.env` file.
- A valid API key is required for usage.
- Filters and analyses are dynamic and adapt to the available data.

## Credits
This project was developed by Cmdr JanJonTheo.

## Disclaimer
This project is not affiliated with or endorsed by Frontier Developments Inc., the creators of Elite Dangerous.

## Special Thanks
Special thanks to Aussi and Cmdr NavlGazr from BGS-Tally for their support and assistance.