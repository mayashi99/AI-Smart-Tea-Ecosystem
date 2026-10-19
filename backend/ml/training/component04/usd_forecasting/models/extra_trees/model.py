from sklearn.ensemble import ExtraTreesRegressor


def create_model():
    return ExtraTreesRegressor(
        n_estimators=250,
        min_samples_leaf=5,
        max_features=0.8,
        random_state=42,
        n_jobs=1,
    )
