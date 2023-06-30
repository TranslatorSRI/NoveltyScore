def find_known_results(response):
    # populate with all inferring sources infores ids
    inferring_sources = []
    known_result_ids = set()
    unknown_result_ids = set()
    key_list = ['results', 'knowledge_graph', 'query_graph']
    if set(key_list).issubset(response['message'].keys()):
        results = response["message"]["results"]
        knowledge_graph = response["message"]["knowledge_graph"]
        pinned_node_ids = []
        qnodes = response["message"]["query_graph"]["nodes"]
        for node_id in qnodes:
            if "ids" in qnodes[node_id] and qnodes[node_id]["ids"]:
                pinned_node_ids.append(node_id)
        for result in results:
            for nb_key in result["node_bindings"]:
                if nb_key not in pinned_node_ids:
                    for nb in result["node_bindings"][nb_key]:
                        unknown_result_ids.add(nb["id"])
            is_result_known(known_result_ids, unknown_result_ids, knowledge_graph, result, pinned_node_ids, inferring_sources)

    #do stuff
    else:
        pass

    return known_result_ids, unknown_result_ids

def is_result_known(known_result_ids, unknown_result_ids, knowledge_graph, result, pinned_node_ids, inferring_sources):
    for analysis in result["analyses"]:
        for eb in analysis["edge_bindings"].values():
            for element in eb:
                edge_id = element["id"]
                edge = knowledge_graph["edges"][edge_id]
                for source in edge["sources"]:
                    if source["resource_role"] == "primary_knowledge_source":
                        if source["resource_id"] not in inferring_sources:
                            for nb_key in result["node_bindings"]:
                                if nb_key not in pinned_node_ids:
                                    for nb in result["node_bindings"][nb_key]:
                                        known_result_ids.add(nb["id"])
                                        unknown_result_ids.remove(nb["id"])
                                    return
