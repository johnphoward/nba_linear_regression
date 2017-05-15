from pyspark import SparkContext
from game_lineup_collector import DataCollector


sc = SparkContext(appName='Parallel NBA Regressions')
sc.setLogLevel('ERROR')

collector = DataCollector()
raw_matchups = collector.load_raw_data()

matchups_RDD = sc.parallelize(raw_matchups, ).map(lambda m: (m.matchup_id, m)).cache()



print matchups_RDD.count()
print matchups_RDD.take(5)
aggregate_RDD = matchups_RDD.map(lambda m: (m.matchup_id, m)).reduceByKey(lambda a, b: a.combine_with_same_matchup(b))
print aggregate_RDD.count()
ordered = aggregate_RDD.takeOrdered(5, lambda (id, m): -m.seconds_played)
for i, m in ordered:
    print m.seconds_played
    print m.games_played
    print m.team_1_stats
    print m.team_2_stats