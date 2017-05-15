import json
import pickle
import requests
from matchup import Matchup


class DataCollector:
    PLAYER_1_ID = 13
    PLAYER_1_TM_ID = 15
    PLAYER_2_ID = 20
    PLAYER_2_TM_ID = 22
    SUB_CODE = 8
    END_PERIOD_CODE = 13

    def __init__(self):
        self.nba_stats_base_url = 'http://stats.nba.com/stats/'
        self.play_by_play_endpoint = 'playbyplayv2'
        self.lineup_endpoint = 'teamdashlineups'
        self.base_pbp_params = {
            'StartPeriod': 1,
            'EndPeriod': 10,
        }
        self.base_lineup_params = {
            'DateFrom': '',
            'DateTo': '',
            'GameSegment': '',
            'GroupQuantity': 5,
            'LastNGames': 0,
            'LeagueID': '00',
            'Location': '',
            'MeasureType': 'Base',
            'Month': '0',
            'OpponentTeamID': '0',
            'Outcome': '',
            'PORound': 0,
            'PaceAdjust': 'N',
            'PerMode': 'PerGame',
            'Period': 0,
            'PlusMinus': 'N',
            'Rank': 'N',
            'Season': '2016-17',
            'SeasonSegment': '',
            'SeasonType': 'Regular+Season',
            'VsConference': '',
            'VsDivision': '',
        }

        self.request_headers = {
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 Chrome/45.0.2454.101 Safari/537.36',
            'Host': 'stats.nba.com',
            'Referer': 'http://stats.nba.com/game/',
            'Connection': 'keep-alive'
        }

    def gather_single_game_lineups(self, game_id):
        """
        Given a stats.nba.com game ID number, gather all the lineups from that game
        Return a list of lineups containing all matchups between the teams and the relevant stats from those matchups
        """
        # try:
        # first get the play by play data
        pbp_headers, pbp_data = self.get_play_by_play_data(game_id)

        p1_index = self.PLAYER_1_TM_ID
        team_1_id, team_2_id = tuple({play[p1_index] for play in pbp_data if play[p1_index] is not None})
        end_period_row_numbers = [index for index, row in enumerate(pbp_data) if row[2] == self.END_PERIOD_CODE]

        all_matchups = []

        # loop through each period (quarter/OT) and get the relevant lineups for each
        for period_index in range(len(end_period_row_numbers)):
            period_number = period_index + 1

            start_index = 0 if period_index == 0 else end_period_row_numbers[period_index - 1] + 1
            end_index = end_period_row_numbers[period_index]
            plays_in_period = pbp_data[start_index: end_index]

            period_lineups = self.parse_out_lineups_for_period(period_number, plays_in_period, team_1_id, team_2_id)
            all_matchups += period_lineups

        return all_matchups

        # except Exception as e:
        #     print "Error encountered"
        #     print e

    def get_starting_matchups(self, plays, team_1_id, team_2_id, period):
        """
        Reads through plays to determine which players started period on the floor.
        Gets help from stats.nba.com lineup endpoint if necessary.
        Returns a new Matchup of the ten players that start on the floor
        """
        team_1_starters, team_2_starters = [], []
        substitution_plays = [play for play in plays if play[2] == self.SUB_CODE]
        subbed_in = set()

        # get id of all players that sub out and add to list if they started the period on the floor
        for sub_play in substitution_plays:
            team_list = team_1_starters if sub_play[self.PLAYER_1_TM_ID] == team_1_id else team_2_starters

            out_id = sub_play[self.PLAYER_1_ID]
            in_id = sub_play[self.PLAYER_2_ID]

            if out_id not in subbed_in:
                team_list.append(out_id)
            subbed_in.add(in_id)

        game_id = plays[0][0]

        # find all
        if len(team_1_starters) < 5:
            common_players = self.get_common_players_from_lineups(game_id, team_1_id, period)
            team_1_starters = team_1_starters + common_players
        if len(team_2_starters) < 5:
            common_players = self.get_common_players_from_lineups(game_id, team_2_id, period)
            team_2_starters = team_2_starters + common_players

        return Matchup(game_id, team_1_id, team_1_starters, team_2_id, team_2_starters)

    def get_common_players_from_lineups(self, game_id, team_id, period):
        """
        Get lineups from a given period and find all players who appeared in all of them
        """
        lineups = self.get_lineup_data(game_id, team_id, period)
        player_ids = [set(lineup[1].split(' - ')) for lineup in lineups]
        return list(map(int, set.intersection(*player_ids)))

    def parse_out_lineups_for_period(self, period, plays_list, first_team_id, second_team_id):
        """
        Parse through plays to return all the matchups for a given period
        """
        all_matchups = []
        matchup = self.get_starting_matchups(plays_list, first_team_id, second_team_id, period)

        for play in plays_list:
            if play[2] == self.SUB_CODE:
                # add matchup to list and get next one in case of substitution
                all_matchups.append(matchup)
                matchup = Matchup.get_new_substitute_lineup(matchup, play)
            else:
                # matchup object internally handles play parsing
                matchup.parse_play_for_stats(play)

        all_matchups.append(matchup)

        return filter(lambda m: m.seconds_played > 0, all_matchups)

    def build_request_url(self, endpoint, params):
        """
        Build request for stats.nba.com api given the specific endpoint and parameters
        return complete URL for GET request
        """
        url_base = self.nba_stats_base_url + endpoint + '?'
        param_string = '&'.join([param_name + '=' + str(param) for param_name, param in params.items()])
        return url_base + param_string

    def get_play_by_play_data(self, game_id):
        """
        Make request to get play by play data and return appropriate data.
        """
        parameters = self.base_pbp_params.copy()
        parameters['GameID'] = game_id
        url = self.build_request_url(self.play_by_play_endpoint, parameters)

        response = requests.get(url, headers=self.request_headers, timeout=5)
        data = json.loads(response.content)['resultSets'][0]
        return data['headers'], data['rowSet']

    def get_lineup_data(self, game_id, team_id, period=0):
        """
        Make request to get lineup data and return appropriate data.
        """
        parameters = self.base_lineup_params.copy()
        parameters['GameID'] = game_id
        parameters['TeamID'] = team_id
        parameters['Period'] = period
        url = self.build_request_url(self.lineup_endpoint, parameters)

        response = requests.get(url, headers=self.request_headers)
        return json.loads(response.content)['resultSets'][1]['rowSet']

    def gather_and_save_season_sequentially(self, season, resume_point=0):
        game_ids = self.get_season_schedule(season)

        if resume_point > 0:
            raw_matchups = self.load_raw_data()
        else:
            raw_matchups = []
        for index, game_id in enumerate(game_ids[resume_point:]):
            print index + resume_point, game_id
            raw_matchups += collector.gather_single_game_lineups(game_id)
            with open('raw_data.pickle', 'w') as f:
                f.write(str([pickle.dumps(matchup) for matchup in raw_matchups]))
            f.close()

    def get_season_schedule(self, season):
        """
        Make request to get list of all games in a given season. Note: currently only available for 2016, 2015
        """
        base_url = 'http://data.nba.com/data/10s/v2015/json/mobile_teams/nba/{season}/league/00_full_schedule.json'
        url = base_url.format(season=season)
        headers = self.request_headers
        headers['referer'] = 'http://stats.nba.com/schedule'
        response = requests.get(url)
        data = response.json()

        schedule_list = []

        for month_dict in data['lscd']:
            schedule_list += [str(game['gid']) for game in month_dict['mscd']['g'] if game['gid'].startswith('002')]

        return schedule_list

    @staticmethod
    def load_raw_data():
        with open('raw_data.pickle', 'r') as f:
            saved_text = f.read()
        f.close()
        pickled_list = eval(saved_text)
        return [pickle.loads(matchup) for matchup in pickled_list]

if __name__ == '__main__':
    collector = DataCollector()
    # collector.gather_and_save_season_sequentially('2016', 852)
