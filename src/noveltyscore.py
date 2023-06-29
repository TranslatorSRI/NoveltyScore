from ars import retrieve_ars_results
from known import find_known_results
from recency import calculate_recency
from nn_distance import calculate_nn_distance

def calculate_novelty_score(known, unknown, nn_distance, recency, response):
    novelty_scores = {}
    ## do stuff
    return novelty_scores

def run_score(pk):
    results = retrieve_ars_results(pk)
    for ars, response in results.items():
        known, unknown = find_known_results(response)
        nn_distance = calculate_nn_distance(known, unknown, minimum_similarity=0.5, num_neighbors=1) #similarity and num neighbors filters could be changed.
        recency = calculate_recency(known, response)
        novelty_scores = calculate_novelty_score(known, unknown, nn_distance, recency, response)

if __name__ == "__main__":
    #These are some KPs run in CI 6/7/2023
    PK = "35d7c9f8-d119-4460-b958-d20aabc37f63" #Treats Multiple Sclerosis
    #PK = "debec37a-a281-47a5-a3d6-dc31206c571f" # Treats Castleman Disease
    #PK = "ae55bac4-80c4-430b-99de-f8ec3bcf55d5" # Treats Infantile Hypercalcemia
    #PK = "825834f8-8b82-4a9f-b963-f629018473c1" # Upregulates OPRM1
    #PK = "88a9bced-1256-44cc-8e08-147456f56637" # Downregulates DRD2
    run_score(PK)
