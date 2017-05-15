from copy import copy


class Matchup:
    PLAYER_1_ID = 13
    PLAYER_1_TM_ID = 15
    PLAYER_2_ID = 20
    PLAYER_2_TM_ID = 22

    PERIOD_START = 12
    JUMP_BALL = 10
    MADE_SHOT = 1
    MISSED_SHOT = 2
    FT = 3
    REBOUND = 4
    TURNOVER = 5
    FOUL = 6
    TIMEOUT = 9

    DEFAULT_STATS = {
        'FGM': 0,
        'FGA': 0,
        'FG_PCT': 0,
        'FG3M': 0,
        'FG3A': 0,
        'FG3_PCT': 0,
        'FTM': 0,
        'FTA': 0,
        'FT_PCT': 0,
        'OREB': 0,
        'DREB': 0,
        'REB': 0,
        'AST': 0,
        'TOV': 0,
        'STL': 0,
        'BLK': 0,
        'BLKA': 0,
        'PF': 0,
        'PFD': 0,
        'PTS': 0,
        'PLUS_MINUS': 0,
    }

    def __init__(self, game_id, team_1_id, team_1_player_ids, team_2_id, team_2_player_ids):
        self.team_1_id = team_1_id
        self.team_1_player_ids = team_1_player_ids
        self.team_1_stats = self.DEFAULT_STATS.copy()

        self.team_2_id = team_2_id
        self.team_2_player_ids = team_2_player_ids
        self.team_2_stats = self.DEFAULT_STATS.copy()

        # create an ID for equivalence checks - sort all player IDs and hash result for independence from ordering
        self.matchup_id = hash(tuple(sorted(self.team_1_player_ids + self.team_2_player_ids)))
        
        self.game_ids = [game_id]

        self.games_played = 1
        self.seconds_played = 0
        self.minutes_played = 0
        self.last_timestamp = None
        self.last_offensive_team = None
        
    def has_same_matchups(self, other_matchup):
        return self.matchup_id == other_matchup.matchup_id
    
    def combine_with_same_matchup(self, other_matchup):
        if not self.has_same_matchups(other_matchup):
            raise ValueError('Mathups cannot be combined- players do not match')
        
        if other_matchup.team_1_id == self.team_1_id:
            self.team_1_stats = self.combine_stats(self.team_1_stats, other_matchup.team_1_stats)
            self.team_2_stats = self.combine_stats(self.team_2_stats, other_matchup.team_2_stats)
        else:
            self.team_1_stats = self.combine_stats(self.team_1_stats, other_matchup.team_2_stats)
            self.team_2_stats = self.combine_stats(self.team_2_stats, other_matchup.team_1_stats)

        self.game_ids = list(set(self.game_ids + other_matchup.game_ids))
        self.games_played = len(self.game_ids)
        self.seconds_played += other_matchup.seconds_played
        self.minutes_played = round(self.seconds_played / 60, 1)

        return self
        
    @staticmethod
    def combine_stats(stats_a, stats_b):
        """
        Given two dictionaries of matchup stats, combine them into one dictionary according to basketball logic
        """
        for key, value in stats_b.items():
            stats_a[key] += value

        stats_a['FG_PCT'] = stats_a['FGM'] * 1.0 / stats_a['FGA'] if stats_a['FGA'] > 0 else 0.00
        stats_a['FG3_PCT'] = stats_a['FG3M'] / stats_a['FG3A'] if stats_a['FG3A'] > 0 else 0.00
        stats_a['FT_PCT'] = stats_a['FTM'] * 1.0 / stats_a['FTA'] if stats_a['FTA'] > 0 else 0.00
        
        return stats_a

    @classmethod
    def get_new_substitute_lineup(cls, matchup, play):
        """
        Substitute one player in and return a new Matchup object
        """
        team_1_players = copy(matchup.team_1_player_ids)
        team_2_players = copy(matchup.team_2_player_ids)

        players_to_update = team_1_players if play[Matchup.PLAYER_1_TM_ID] == matchup.team_1_id else team_2_players

        out_id = play[Matchup.PLAYER_1_ID]
        in_id = play[Matchup.PLAYER_2_ID]
        player_index = players_to_update.index(out_id)
        players_to_update[player_index] = in_id
        
        game_id = matchup.game_ids[0]

        new_matchup = cls(game_id, matchup.team_1_id, team_1_players, matchup.team_2_id, team_2_players)

        new_matchup.last_timestamp = cls.timestamp_to_seconds(play[6])

        return new_matchup

    @staticmethod
    def timestamp_to_seconds(timestamp):
        minutes, seconds = timestamp.split(':')
        return round(int(minutes) * 60 + float(seconds), 1)

    def parse_play_for_stats(self, play):
        play_type = play[2]
        time_of_play = self.timestamp_to_seconds(play[6])
        primary_team = play[self.PLAYER_1_TM_ID]
        play_description = play[7] if play[7] is not None else play[9]
        stats_to_update = self.team_1_stats if primary_team == self.team_1_id else self.team_2_stats
        other_team_stats = self.team_2_stats if primary_team == self.team_1_id else self.team_1_stats

        if play_type == self.MADE_SHOT:
            stats_to_update['FGM'] += 1
            stats_to_update['FGA'] += 1
            stats_to_update['FG_PCT'] = stats_to_update['FGM'] * 1.0 / stats_to_update['FGA']
            stats_to_update['PTS'] += 2

            if '3PT' in play_description:
                stats_to_update['FG3M'] += 1
                stats_to_update['FG3A'] += 1
                stats_to_update['FG3_PCT'] = stats_to_update['FG3M'] * 1.0 / stats_to_update['FG3A']
                stats_to_update['PTS'] += 1

            if play[self.PLAYER_2_TM_ID] is not None:
                stats_to_update['AST'] += 1

            stats_to_update['PLUS_MINUS'] = stats_to_update['PTS'] - other_team_stats['PTS']
            other_team_stats['PLUS_MINUS'] = other_team_stats['PTS'] - stats_to_update['PTS']
        elif play_type == self.MISSED_SHOT:
            stats_to_update['FGA'] += 1
            stats_to_update['FG_PCT'] = stats_to_update['FGM'] * 1.0 / stats_to_update['FGA']

            if '3PT' in play_description:
                stats_to_update['FG3A'] += 1
                stats_to_update['FG3_PCT'] = stats_to_update['FG3M'] / stats_to_update['FG3A']

            if 'BLK' in play_description:
                stats_to_update['BLKA'] += 1
                other_team_stats['BLK'] += 1

            self.last_offensive_team = primary_team

        elif play_type == self.FT:
            stats_to_update['FTA'] += 1

            if 'MISS' not in play_description:
                stats_to_update['FTM'] += 1
                stats_to_update['PTS'] += 1
                stats_to_update['PLUS_MINUS'] = stats_to_update['PTS'] - other_team_stats['PTS']
                other_team_stats['PLUS_MINUS'] = other_team_stats['PTS'] - stats_to_update['PTS']

            stats_to_update['FT_PCT'] = stats_to_update['FTM'] * 1.0 / stats_to_update['FTA']
            self.last_offensive_team = primary_team

        elif play_type == self.REBOUND:
            stats_to_update['REB'] += 1

            if primary_team == self.last_offensive_team:
                stats_to_update['OREB'] += 1
            else:
                stats_to_update['DREB'] += 1

        elif play_type == self.TURNOVER:
            stats_to_update['TOV'] += 1

            if play[self.PLAYER_2_TM_ID] is not None:
                other_team_stats['STL'] += 1

        elif play_type == self.FOUL:
            stats_to_update['PF'] += 1
            other_team_stats['PFD'] += 1

        if play_type is not self.PERIOD_START and self.last_timestamp is not None:
            self.seconds_played += self.last_timestamp - time_of_play
            self.minutes_played = round(self.seconds_played / 60, 1)

        self.last_timestamp = time_of_play

    def calculate_possessions_played(self):
        tm_1_attempts = self.team_1_stats['FGA'] + 0.4 * self.team_1_stats['FTA']
        try:
            tm_1_orebs = 1.07 * (self.team_1_stats['OREB'] * 1.0 / (self.team_1_stats['OREB'] + self.team_1_stats['DREB'])) * (self.team_1_stats['FGA'] - self.team_1_stats['FGM'])
        except ZeroDivisionError:
            tm_1_orebs = 0.0
        tm_1_possessions = tm_1_attempts - tm_1_orebs + self.team_1_stats['TOV']

        tm_2_attempt_term = self.team_2_stats['FGA'] + 0.4 * self.team_2_stats['FTA']
        try:
            tm_2_orebs = 1.07 * (self.team_2_stats['OREB'] * 1.0 / (self.team_2_stats['OREB'] + self.team_2_stats['DREB'])) * (self.team_2_stats['FGA'] - self.team_2_stats['FGM'])
        except ZeroDivisionError:
            tm_2_orebs = 0.0
        tm_2_possessions = tm_2_attempt_term - tm_2_orebs + self.team_2_stats['TOV']

        return (tm_1_possessions + tm_2_possessions) / 2