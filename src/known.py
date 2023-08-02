#!/usr/bin/env python

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
    return known_result_ids, unknown_result_ids
