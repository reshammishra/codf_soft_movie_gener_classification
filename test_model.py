from app import predict_genres

plots = [
    "A group of soldiers fights to survive behind enemy lines during a brutal war.",
    "Two strangers meet in Paris and slowly fall in love over one summer.",
    "A family moves into an old house where terrifying ghosts haunt them every night.",
]

for plot in plots:
    print("\nPlot:", plot)
    for p in predict_genres(plot):
        print(f"   {p['genre']:<16} {p['score']}%")