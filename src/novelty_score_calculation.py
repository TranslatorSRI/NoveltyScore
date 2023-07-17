import pandas as pd
from datetime import date
import json
import requests
from bs4 import BeautifulSoup
import numpy as np
from known import find_known_results
from nn_distance import calculate_nn_distance
"""
This script computes the novelty score for a list of results obtained for a 1-H response.
The steps for the ideal workflow are as follows:
1. Distinguish whether the result is a known result or an unknown result.
2. Compute FDA approval status to check if currently under approval or already approved.
3. Compute recency by noting the associated publications of the result.
4. Compute molecular similarity to identify if similar to existing drugs.
 
The end result of this script displays a table with values from different columns and accordingly lists the novelty score as well.
"""

def sigmoid(x):
    return 1 / (1 + np.exp(x))

def query_id(response):
    if response['fields']['status'] == 'Done':
        for i in response['fields']['data']['message']['query_graph']['nodes']:
            if 'ids' in response['fields']['data']['message']['query_graph']['nodes'][i].keys():
                if response['fields']['data']['message']['query_graph']['nodes'][i]['ids']:
                    known_node = response['fields']['data']['message']['query_graph']['nodes'][i]['categories'][0]
                else:
                    unknown_node = response['fields']['data']['message']['query_graph']['nodes'][i]['categories'][0]
            else:
                unknown_node = response['fields']['data']['message']['query_graph']['nodes'][i]['categories'][0]
        if unknown_node in ['biolink:ChemicalEntity', 'biolink:SmallMolecule', 'biolink:Drug']:
            chk=1
        else:
            chk=0
    return known_node, unknown_node, chk


def recency_function_exp(number_of_publ, age_of_oldest_publ, max_number, max_age):
    """
    Calculates the recency based on number of publications accociated to each drug
    and age of the oldest publication
    
    Args:
        number_of_publ (float): The current number of publications.
        age_of_oldest_publ (float): The current age of the oldest publication.
        max_number (float): The maximum number of publication: e.g. consider 100 for all drugs.
        max_age (float): The publication with the recent 50 years have been considered.
    
    Returns:
        float: The recency value of z.
    """
    coef_number = 10
    coef_age = 4
    alter_number_of_publ = sigmoid(coef_number * (number_of_publ / max_number - 0.5))
    alter_age_of_oldest_publ = sigmoid(coef_age * (age_of_oldest_publ / max_age - 0.5))

    if np.isnan(number_of_publ) and not np.isnan(age_of_oldest_publ):
        recency = alter_age_of_oldest_publ
    elif np.isnan(age_of_oldest_publ) and not np.isnan(number_of_publ):
        recency = alter_number_of_publ
    else:
        recency = alter_number_of_publ * alter_age_of_oldest_publ
    
    return recency


def extract_year_pmid(response):
    """
    Extracting the publication year from the XML response, assuming a specific structure.
    Note that : the structure of the XML response can vary, leading to cases where the publication year
    may not be found in the expected location.
    
    Args:
        response which is a GET request from the URL pointing to the XML of a PMID
        
    Returns:
        Date (Year) of the publishing date
    
    """
    soup = BeautifulSoup(response.content, 'xml')

    try:
        year = None

        # Check if year is present in PubDate element
        pub_date = soup.find('PubDate')
        if pub_date:
            year_element = pub_date.find('Year')
            if year_element:
                year = year_element.text

        # If year is not found, check alternative elements
        if not year:
            date_completed = soup.find('DateCompleted')
            if date_completed:
                year_element = date_completed.find('Year')
                if year_element:
                    year = year_element.text

            pub_date_revision = soup.find('PubDate', pubstatus='revised')
            if pub_date_revision:
                year_element = pub_date_revision.find('Year')
                if year_element:
                    year = year_element.text

        return year
    except AttributeError:
        return None


def extract_year_pmc(response):
    """
    Extracting the publication year from the XML response, assuming a specific structure.
    Note that : the structure of the XML response can vary, leading to cases where the publication year
    may not be found in the expected location.
    
    Args:
        response which is a GET request from the URL pointing to the XML of a PMC ID
        
    Returns:
        Date (Year) of the publishing date
    
    """
    soup = BeautifulSoup(response.content, 'xml')

    try:
        year = soup.find('pub-date').find('year').text
        return int(year)
    except AttributeError:
        try:
            year = soup.find('pub-date').find('Year').text
            return year
        except AttributeError:
            return None


def get_publication_year_pmid(pmid):
    """
    Args: PMID
    
    Returns: The "Year" of publishing date
    """
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id="
    full_url = f"{base_url}{pmid}"
    response = requests.get(full_url)
    return extract_year_pmid(response)

def get_publication_year_pmc(pmc_id):
    """
    Args: PMC ID
    
    Returns: The "Year" of publishing date
    """
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id="
    full_url = f"{base_url}{pmc_id}"
    response = requests.get(full_url)
    return extract_year_pmc(response)


def extracting_drug_fda_publ_date(response):
    """
    Upon querying, the response is returned as a list containing 10 dictionaries,
    with each dictionary representing the response from an ARA. The function 'extracting_drug_fda_publ_date'
    is designed to extract the drug entity name of each edge. It then checks the EPC attributes of each edge
    to determine the FDA approval status of the drug and the accociated pulications PMID/PMC ID ... .
    And finally extract the publishing date of the publications to get the oldest (Year) date among them.

    Args:
        Dictionary: response for a ARA to a query

    Returns:
        "An DataFrame constructed where each row represents an edge and contains information such as the drug entity
        name, FDA status of the drug, a list of associated publications, the number of associated publications,
        and the oldest publication date (year) linked to each drug."

    """
    attribute_type_id_list_fda = ['biolink:FDA_approval_status', 'biolink:FDA_APPROVAL_STATUS']
    attribute_type_id_list_pub = ['biolink:publications', 'biolink:Publication', 'biolink:publication']
    drug_idx_fda_status = []
    keys_list = ['results', 'knowledge_graph', 'query_graph']
    today = date.today()

    if response['fields']['status'] == 'Done':
        if set(keys_list).issubset(response['fields']['data']['message'].keys()):
            res_chk = 1
            # for edge in response['fields']['data']['message']['knowledge_graph']['edges'].keys():
            query_known, query_unknown, query_chk = query_id(response)
            edge_list = list(response['fields']['data']['message']['knowledge_graph']['edges'].keys())
            for idx, idi in enumerate(edge_list):
                if idx % 20 == 0:
                    print(f'progressing {idx}')
                edge = edge_list[idx]
                edge_attribute = response['fields']['data']['message']['knowledge_graph']['edges'][edge]
                # if set(['subject', 'object']).issubset(edge_attribute.keys()):
                if query_chk==1:
                    if 'PUBCHEM' in edge_attribute['subject'] or 'CHEMBL' in edge_attribute['subject'] or 'UNII' in edge_attribute['subject'] or 'RXNORM' in edge_attribute['subject']:
                        drug_idx = edge_attribute['subject']
                    else:
                        drug_idx = edge_attribute['object']
                    if set(['attributes']).issubset(edge_attribute.keys()):
                        if len(edge_attribute['attributes']) > 0:
                            att_type_id = {}
                            fda = []
                            pub = []
                            for i in range(len(edge_attribute['attributes'])):
                                att_type_id[i] = edge_attribute['attributes'][i]['attribute_type_id']
                            # print(att_type_id)

                            for key in att_type_id.keys():
                                if att_type_id[key] in attribute_type_id_list_fda:
                                    fda.append(key)
                                elif att_type_id[key] in attribute_type_id_list_pub:
                                    pub.append(key)
                            # print(fda)
                            # print(pub)

                            if len(fda) > 0:
                                if edge_attribute['attributes'][fda[0]]['value'] == 'FDA Approval':
                                    fda_status = 0.0
                                else:
                                    fda_status = 1.0
                            else:
                                fda_status = None

                            # Publication
                            if len(pub) > 0:
                                publications = edge_attribute['attributes'][pub[0]]['value']
                                number_of_publ = len(publications)
                                publications = tuple(publications)
                                ## Extracting the year of publishing of each PMID or PMC_ID
                                if len(publications) > 0:
                                    year_published = []
                                    for publ in publications:
                                        if 'PMID' in publ:
                                            year = get_publication_year_pmid(publ[5:])
                                            year_published.append(year)
                                        elif 'PMC' in publ:
                                            year = get_publication_year_pmc(publ)
                                            year_published.append(year)
                                        else:
                                            age_oldest = np.nan

                                    Years = [int(year) for year in year_published if year and str(year).isdigit()]
                                    if len(Years) > 0:
                                        age_oldest = today.year - min(Years)
                                        # drug_idx_fda_status.append(
                                        #     (edge, drug_idx, fda_status, publications, number_of_publ, age_oldest))

                                    else:
                                        age_oldest = np.nan
                                    # print(age_oldest)
                                else:
                                    age_oldest = np.nan
                                # drug_idx_fda_status.append(
                                #     (edge, drug_idx, fda_status, publications, number_of_publ, age_oldest))

                            else:
                                publications = None
                                number_of_publ = 0.0
                                age_oldest = np.nan
                                # drug_idx_fda_status.append(
                                #     (edge, drug_idx, fda_status, publications, number_of_publ, age_oldest))
                        drug_idx_fda_status.append((idi, drug_idx, fda_status, publications, number_of_publ, age_oldest))
                else:
                    if query_unknown in ['biolink:Gene', 'biolink:Protein']:
                        if 'NCBI' in edge_attribute['subject'] or 'GO' in edge_attribute['subject']:
                            gene_idx = edge_attribute['subject']
                        else:
                            gene_idx = edge_attribute['object']
                        drug_idx_fda_status.append((idi, gene_idx))
                    elif query_unknown in ['biolink:Disease', 'biolink:Phenotype']:
                        if 'MONDO' in edge_attribute['subject']:
                            dis_idx = edge_attribute['subject']
                        else:
                            dis_idx = edge_attribute['object']
                        drug_idx_fda_status.append((idi, dis_idx))
        else:
            res_chk = 0
            query_chk = 0
    else:
        res_chk = 0
        query_chk = 0
    if query_chk==1 and res_chk==1:
        DF = pd.DataFrame(drug_idx_fda_status, columns=['edge', 'drug', 'fda status', 'publications', 'number_of_publ', 'age_oldest_pub'])
    elif query_chk!=1 and res_chk==1:
        DF = pd.DataFrame(drug_idx_fda_status, columns=['edge', 'result'])
    else:
        DF = pd.DataFrame()
    return DF, query_chk

def extract_results(response, unknown, known):
    results = []
    results_known = []
    kid, ukid = 0, 0
    if response['fields']['status'] == 'Done':
        for idi, i in enumerate(response['fields']['data']['message']['results']):
            if idi in unknown:
                results.append([])
                for idj, j in enumerate(i['analyses']):
                    for idk, k in enumerate(j['edge_bindings'][list(j['edge_bindings'].keys())[0]]):
                        results[ukid].append(k['id'])
                ukid+=1

            elif idi in known:
                results_known.append([])
                for idj, j in enumerate(i['analyses']):
                    for idk, k in enumerate(j['edge_bindings'][list(j['edge_bindings'].keys())[0]]):
                        results_known[kid].append(k['id'])
                kid+=1
    return results, results_known

def result_edge_correlation(results, results_known, df):
    df_res = pd.DataFrame()
    res_known = set()
    res_unknown = set()
    for idi, i in enumerate(results):
        for j in i:
            df_res = pd.concat([df_res, df[df['edge']==j]])
            res_unknown.add(df.loc[df['edge']==j, 'drug'].iloc[0])

    for idi, i in enumerate(results_known):
        for j in i:
            res_known.add(df.loc[df['edge']==j, 'drug'].iloc[0])
    return df_res, res_unknown, res_known

def novelty_score(fda_status, recency, similarity):
    """
    Calculate the novelty score for each drug entity based on FDA status, recency and similarity of the drug.
    
    FDA status 0 | 1 
        --> 0 to be FDA approved
    0 < recency < 1 
        --> 1 to have a high recency where the publications are so new and number of publications is too few. 
    0 < similarity < 1
        --> 0 to have a very low molecular structure similarity, so it is novel.
        
    Args:
        float: fda_status
        float: recency
        float: similarity
    
    Returns:
        float: novelty_score
    
    """
    if not np.isnan(recency):
        score = recency
        if not np.isnan(similarity):
            similarity = 1 - similarity
            if similarity > 0.5:
                score = score*(0.73+similarity)
            if score>1:
                score=1        
            if fda_status == 0:
                score=score*0.85 
    else:
        if np.isnan(similarity): 
            score=0 
        else:
            score=(1-similarity)
    return score

def compute_novelty(response):
    """ INPUT: JSON Response with merged annotated results for a 1-H query

    1. load the json file
    2. Give the json to extracting_drug_fda_publ_date(response) function to extract the EPC
    3. Apply the recency function of df, to add a new column as recency to the dataframe
    4. Add a new column to the df as similarity which has random number between 0-1
    5. Now the dataframe df is ready for applying the novelty score on it

    STEP for Known/Unknown will be added in the future

    OUTPUT: Pandas DataFrame  with FDA Status, Recency, Similarity and Novelty score per result
    """
    # Step 1
    mergedAnnotatedOutput = json.load(open(response))
    if mergedAnnotatedOutput['fields']['status'] == 'Done':
        if mergedAnnotatedOutput['fields']['data']['message']['results']:
            known, unknown = find_known_results(mergedAnnotatedOutput)
            #
            # # Step 2

            df, query_chk = extracting_drug_fda_publ_date(mergedAnnotatedOutput)
            # print(df.head())
            # print(query_chk)

            df.to_excel(f'DATAFRAME_{i}.xlsx', header=False, index=False)
            # df = pd.read_excel('DATAFRAME.xlsx', names=['edge', 'drug', 'fda status', 'publications', 'number_of_publ', 'age_oldest_pub'])
            # query_chk = 1

            # #
            res, res_known = extract_results(mergedAnnotatedOutput, unknown, known)
            # print(len(res_known))
            # print(len(res))
            # # #
            df_res, res_unknown, res_known = result_edge_correlation(res, res_known, df)
            # print(len(res_unknown))
            # print(len(res_known))
            df = df_res

            if query_chk==1:
                # Step 3:
                # calculating the recency
                df['recency'] = df.apply(lambda row: recency_function_exp(row['number_of_publ'], row['age_oldest_pub'], 100, 50) if not (np.isnan(row['number_of_publ']) or np.isnan(row['age_oldest_pub'])) else np.nan, axis=1)
                #
                # # Step 4:
                # # This section will be added later. Currently just putting 'NaN':
                # nearest_neighbours = calculate_nn_distance(res_known, res_unknown, 0, 1)
                # df['similarity'] = [nearest_neighbours[row['drug']] if row['drug'] in nearest_neighbours.keys() else np.nan for row in df.rows ]
                df = df.assign(similarity=np.nan)

                # # Step 5:
                # # Calculating the novelty score:
                df['novelty_score'] = df.apply(lambda row: novelty_score(row['fda status'], row['recency'], row['similarity']), axis=1)
                df_res.to_excel(f'DATAFRAME_result_{i}.xlsx', header=False, index=False)

                # # # Step 6
                # # # Just sort them:
                df = df[['drug', 'novelty_score']].sort_values(by= 'novelty_score', ascending= False)
            else:
                df = df.assign(novelty_score=0)
            df.to_excel(f'DATAFRAME_NOVELTY_{i}.xlsx', header=False, index=False)
        else:
            df = pd.DataFrame()
    else:
        df = pd.DataFrame()
    return df

for i in list(range(1, 10)):
    temp = compute_novelty(f'dictionary_{i}.json')
    if temp.empty:
        print(f"No Results in dictionary_{i}.json")
    else:
        temp_json = temp.to_json(f'NoveltyScore_{i}.json', orient='index')
