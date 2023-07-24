# def is_result_known(known_result_ids, unknown_result_ids, knowledge_graph, result, pinned_node_ids, inferring_sources):
#     for analysis in result["analyses"]:
#         for eb in analysis["edge_bindings"].values():
#             for element in eb:
#                 edge_id = element["id"]
#                 edge = knowledge_graph["edges"][edge_id]
#                 for source in edge["sources"]:
#                     if source["resource_role"] == "primary_knowledge_source":
#                         if source["resource_id"] not in inferring_sources:
#                             for nb_key in result["node_bindings"]:
#                                 if nb_key not in pinned_node_ids:
#                                     for nb in result["node_bindings"][nb_key]:
#                                         known_result_ids.add(nb["id"])
#                                         unknown_result_ids.remove(nb["id"])
#                                     return

import json


def find_known_results(response):
    inferring_sources = ['infores:aragorn', 'infores:arax', 'infores:biothings-explorer',
                         'infores:improving-agent', 'infores:robokop']
    known_result_ids = []
    unknown_result_ids = []
    key_list = ['results', 'knowledge_graph', 'query_graph']
    if set(key_list).issubset(response['fields']['data']['message'].keys()):
        results = response['fields']['data']["message"]["results"]
        knowledge_graph = response['fields']['data']["message"]["knowledge_graph"]
        # pinned_node_ids = []
        # qnodes = response['fields']['data']["message"]["query_graph"]["nodes"]
        # for node_id in qnodes:
        #     if "ids" in qnodes[node_id] and qnodes[node_id]["ids"]:
        #         pinned_node_ids.append(node_id)
        for idres, result in enumerate(results):
            if 'analyses' in result.keys():
                for analysis in result["analyses"]:
                    for eb in analysis["edge_bindings"].values():
                        for element in eb:
                            edge_id = element["id"]
                            edge = knowledge_graph["edges"][edge_id]
                            for source in edge["sources"]:
                                if source["resource_role"] == "primary_knowledge_source":
                                    if source["resource_id"] not in inferring_sources:
                                        known_result_ids.append(idres)
                                        break
                                    else:
                                        unknown_result_ids.append(idres)
                                        # for nb_key in result["node_bindings"]:
                                        #     if nb_key not in pinned_node_ids:
                                        #         for nb in result["node_bindings"][nb_key]:
                                        #             known_result_ids.add(nb["id"])
                                        #             unknown_result_ids.remove(nb["id"])
                # for nb_key in result["node_bindings"]:
                #     if nb_key not in pinned_node_ids:
                #         for nb in result["node_bindings"][nb_key]:
                #             unknown_result_ids.add(nb["id"])
                # print(result["node_bindings"])
                # print(pinned_node_ids)
                # print(unknown_result_ids, known_result_ids)
                # is_result_known(known_result_ids, unknown_result_ids, knowledge_graph, result, pinned_node_ids, inferring_sources)
                # print(unknown_result_ids, known_result_ids)
                # print("\n")
                # if idres==14:
                #     break
    return known_result_ids, unknown_result_ids


# mergedAnnotatedOutput = json.load(open('../mergedAnnotatedOutput.json'))
# known, unknown = find_known_results(mergedAnnotatedOutput)

