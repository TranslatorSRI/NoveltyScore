import pandas as pd
from datetime import date
import json
import requests
from bs4 import BeautifulSoup
import numpy as np

"""
This script computes the novelty score for a list of results obtained for a 1-H response.
The steps for the ideal workflow are as follows:
1. Distinguish whether the result is a known result or an unknown result. (Currently not implemented but will be added in the future)
2. Compute FDA approval status to check if currently under approval or already approved.
3. Compute recency by noting the associated publications of the result.
4. Compute molecular similarity to identify if similar to existing drugs. (Currently not implemented but will be added in the future)
 
The end result of this script displays a table with values from different columns and accordingly lists the novelty score as well.
"""



# url = "https://ars.ci.transltr.io/ars/api/messages/"
# response = requests.get(url)
# #
# if response.status_code == 200:
#     # save it to a file
#     with open("mergedAnnotatedOutput.json", "w") as file:
#         file.write(response.text)
#     print("JSON file downloaded successfully.")
# else:
#     print("Failed to download the JSON file.")


def sigmoid(x):
    return 1 / (1 + np.exp(x))


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
            #for edge in response['fields']['data']['message']['knowledge_graph']['edges'].keys():
            edge_list = list(response['fields']['data']['message']['knowledge_graph']['edges'].keys())
            # Juts for testing we get the edges by index here:
            for idx in range(len(edge_list)):
                edge = edge_list[idx]
                edge_attribute = response['fields']['data']['message']['knowledge_graph']['edges'][edge]
                if set(['subject', 'object']).issubset(edge_attribute.keys()):
                    if 'MONDO' in edge_attribute['subject']:
                        drug_idx = edge_attribute['object']
                    else:
                        drug_idx = edge_attribute['subject']
                    if set(['attributes']).issubset(edge_attribute.keys()):
                        if len(edge_attribute['attributes']) > 0:
                            for attribute in edge_attribute['attributes']:
                                if attribute['attribute_type_id'] in attribute_type_id_list_fda:
                                    if attribute['value'] == 'FDA Approval':
                                        fda_status = 0.0
                                    else:
                                        fda_status = 1.0
                                    break
                                else:
                                    fda_status = None
                                # publications:
                                if attribute['attribute_type_id'] in attribute_type_id_list_pub:
                                    publications = attribute['value']
                                    publications = tuple(publications)
                                    number_of_publ = len(attribute['value'])
                                    ## Extracting the year of publishing of each PMID or PMC_ID
                                    if number_of_publ > 0.0:
                                        year_published = []
                                        for pub in publications:
                                            if 'PMID' in pub:
                                                year = get_publication_year_pmid(pub[5:])
                                                year_published.append(year)
                                            elif 'PMC' in pub:
                                                year = get_publication_year_pmc(pub)
                                                year_published.append(year)
                                            else:
                                                pass
                                            #year_published.append(year)
                                        #print(edge)
                                        print(year_published)
                                        Years = [int(year) for year in year_published if year and str(year).isdigit()]
                                        if len(Years) > 0:
                                            age_oldest = today.year - min(Years)
                                        else:
                                            pass
                                        print(age_oldest)
                                    else:
                                        age_oldest = np.nan
                                    #drug_idx_fda_status.append((edge, drug_idx, fda_status, publications, number_of_publ, year_oldest))
                                else:
                                    publications = None
                                    number_of_publ = 0.0
                                    age_oldest = np.nan
                                drug_idx_fda_status.append((edge, drug_idx, fda_status, publications, number_of_publ, age_oldest))
                        else:
                            fda_status = None
                        #drug_idx_fda_status.append((edge, drug_idx, fda_status, publications, number_of_publ, year_oldest))
                    else:
                        pass
                    drug_idx_fda_status.append((edge, drug_idx, fda_status, publications, number_of_publ, age_oldest))
    
    DF = pd.DataFrame(drug_idx_fda_status, columns= ['edge', 'drug', 'fda status', 'publications', 'number_of_publ', 'age_oldest_pub'])
    DF = DF.reset_index(drop=True)
    DF = DF.drop_duplicates(ignore_index= True)
    return DF


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
    2. Give the mergedAnnotatedOutput1 to extracting_drug_fda_publ_date(response) function to extract the EPC
    3. Apply the recency function of df, to add a new column as recency to the dataframe
    4. Add a new column to the df as similarity which has random number between 0 -1
    5. Now the dataframe df is ready for applying the novelty score on it

    STEP for KNown/Unknown will be added in the future

    OUTPUT: Pandas DataFrame  with FDA Status, Recency, Similarity and Novelty score per result
    """
    # Step 1
    mergedAnnotatedOutput = json.load(open(response))

    # Step 2
    df = extracting_drug_fda_publ_date(mergedAnnotatedOutput)

    # Step 3:
    # calculating the recency
    df['recency'] = df.apply(lambda row: recency_function_exp(row['number_of_publ'], row['age_oldest_pub'], 100, 50) if not (np.isnan(row['number_of_publ']) or np.isnan(row['age_oldest_pub'])) else np.nan, axis=1)

    # Step 4:
    # This section will be added later. Currently just putting 'NaN':
    df = df.assign(similarity=np.nan)

    # Step 5:
    # Calculating the novelty score:
    df['novelty_score'] = df.apply(lambda row: novelty_score(row['fda status'], row['recency'], row['similarity']), axis=1)
    print(df.head(15))

    # Step 6
    # Just sort them:
    df = df[['drug', 'fda status', 'recency', 'similarity', 'novelty_score']].sort_values(by= 'novelty_score', ascending= False)
    print(df.head(15))
    return df


temp = compute_novelty('mergedAnnotatedOutput.json')
print(temp.head())
