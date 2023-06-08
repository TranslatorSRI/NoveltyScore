import pickle
from known import find_known_results
import py2neo
import normalize_nodes
from lxml import etree
from collections import defaultdict
import requests
import time

from ars import retrieve_ars_results

utf8_parser = etree.XMLParser(encoding='utf-8')

def getQueryNode(response_json):
    """
    Get the query node from the response_json. Has some security checks for various ARAs.
    """
    query_node = response_json['message']['query_graph']['nodes']

    if 'on' in query_node:
    #Weird gene query
        if query_node['on'].get('categories',[]) == ['biolink:Gene']:
            query_idx = "biolink:Gene"
            disease = False
        elif('ids' in query_node['on']):
            query_idx = query_node['on']['ids'][0]
            disease = True
        else:
            query_idx = "N/A"
            disease = False
    elif 'n0' in query_node:
        if('ids' in query_node['n0']):
            query_idx = query_node['n0']['ids'][0]
            disease = True
        elif('id' in query_node['n1']):
            query_idx = query_node['n1']['id']
            disease = True
        else:
            query_idx = "N/A"
            disease = True
    elif 'disease' in query_node:
        query_idx = query_node['disease']['ids'][0]
        disease = True
    #Could not find any node
    else:
        query_idx = "N/A"
        disease=False
    return (query_idx,disease)
            

def drug_idx_generator(response_json):
    """
    Get the drug identifiers for results from the TRAPI json dump.
    """
    for result in response_json['message'].get('results',[]):
        node_bindings = result['node_bindings']
        if 'sn' in node_bindings:
            drug_idx = node_bindings['sn'][0]['id']
        elif 'n1' in node_bindings:
            drug_idx = node_bindings['n1'][0]['id']
        elif 'drug' in node_bindings:
            drug_idx = node_bindings['drug'][0]['id']
        elif "chemical" in node_bindings:
            drug_idx = node_bindings['chemical'][0]['id']
        else:
            print(node_bindings)
            raise Exception("Could not get Drug")
        
        #NORMALIZE DRUG IDENTIFIER
        #drug_idx = m[drug_idx]
        yield drug_idx
    return

def queryROBOKOPForPMIDsDiseaseDrugList(disease_idx,drug_list):
    '''
    This function uses Py2Neo to query the ROBOKOPKG for each TextMiningKP edge for each pair
    in the disease and drug list we found in the graph.
    '''
    graph = py2neo.Graph(host="robokopkg.renci.org")
    query_template = 'MATCH (d:`biolink:Disease`)-[r]-(c:`biolink:ChemicalEntity`) WHERE d.id=$disease_idx AND c.id in $drug_list AND r.`biolink:primary_knowledge_source`="infores:textminingkp" RETURN c.id, r.publications'
    publications_for_pair = defaultdict(set)
    query_res = graph.run(query_template,parameters={"disease_idx":disease_idx, "drug_list":drug_list})
    for message in query_res:
#        for publication in message['r.publications']:
        c_idx = message['c.id']
        pub_list = message['r.publications']
        publications_for_pair[(disease_idx,c_idx)].update(pub_list)
    return publications_for_pair

def getPublistForPairs(disease_idx,drug_identifier_list):
    """
    Go through a disease and a list of drugs. Search on ROBOKOP for publications from TextMiningKP
    which support a specific (disease,drug) pair. This function mostly handles the lifting of
    normalizing the drug names, and mapping the found results to the 
    """
    pubs_for_pairs = {}
    #queryROBOKOPForPMIDsDiseaseDrugList
    all_pubs = set()
    normalized_drug_dict = normalize_nodes.normalize_big_list(drug_identifier_list)
    normalized_drug_idxs = set()
    for drug_key in drug_identifier_list:
        #Drug_dict[drug_key]==None means the identifier can't be normalized. We won't be able to 
        #find it in ROBOKOP either.
        if(drug_key not in normalized_drug_dict or normalized_drug_dict[drug_key]==None): continue
        else: normalized_drug_idxs.add(normalized_drug_dict[drug_key][0])
            
    publications_from_rk = queryROBOKOPForPMIDsDiseaseDrugList(disease_idx,list(normalized_drug_idxs))
    
    #Denormalize the drug identifier and make a dictonary 
    # for the publications which map to (disease,unnormed_drug_idx).
    denormed_publications = {}
    for drug_key in drug_identifier_list:
        if(drug_key not in normalized_drug_dict or normalized_drug_dict[drug_key]==None): 
            denormed_publications[(disease_idx,drug_key)] = []
        else: 
            drug_idx = normalized_drug_dict[drug_key][0]
            denormed_publications[(disease_idx,drug_key)] = publications_from_rk[(disease_idx,drug_key)]
        all_pubs.update(publications_from_rk[(disease_idx,drug_key)])
    return denormed_publications, all_pubs

def PMCIDsToYear(pmcids):
    """
    Query the Pubmed Eutils API for publication information for the list of PubmedCentral identifiers passed in.
    Builds a dictonary which maps PubmedCentral ID to it's earliest year of publication {PMCXXX: 1990}.
    """

    time.sleep(0.2)
    pmc_api_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id=" + ','.join(pmcids)
    #print(pmc_api_url)
    time.sleep(0.2)
    r = requests.get(pmc_api_url)
    s = r.text.encode('utf-8')
    article_to_year = {}
    if(len(s)>250):
        tree = etree.fromstring(s, parser=utf8_parser)
        for meta_ele in tree.xpath("//article-meta"):
            pmc_idx = "PMC" + meta_ele.xpath("./article-id[@pub-id-type='pmc']/text()")[0]
            #ub-date pub-type="epub">
            pub_year_list = meta_ele.xpath("./pub-date/year/text()")
            earliest_year = min([int(x) for x in pub_year_list])
            article_to_year[pmc_idx] = earliest_year
    return article_to_year

def PMIDsToYear(pmids):
    """
    Query the Pubmed Eutils API for publication information for the list of pubmed identifiers passed in.
    Builds a dictonary which maps Pubmed ID to it's earliest year of publication {PMID:XXX: 1990}.
    """
    time.sleep(0.2)
    pm_api_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=" + ','.join(pmids)
    r = requests.get(pm_api_url)
    s = r.text.encode('utf-8')
    article_to_year = {}
    if(len(s)>250):
        tree = etree.fromstring(s, parser=utf8_parser)
        for article_ele in tree.xpath("//PubmedArticle"):
            pm_idx = "PMID:" + article_ele.xpath("./MedlineCitation/PMID/text()")[0]
            pub_year_list = article_ele.xpath("./PubmedData/History/PubMedPubDate/Year/text()")
            earliest_year = min([int(x) for x in pub_year_list])
            article_to_year[pm_idx] = earliest_year
    return article_to_year

def chunk_list(l):
    for i in range(0,len(l),250):
        lower = i
        upper = min(i+250,len(l))
        yield l[lower:upper]

def getDatesFromPaperIdentifiers(paper_ids):
    """
    This function is mostly a helper function. We take in a large list of paper identifiers.
    We split this list into two camps; Pubmed and PubmedCentral (which must be processed in different
    ways). We then further split these two lists into chunks which are 250 identifiers long. We then 
    stitch the resulting dictonaries together which should have a date for every paper passed in 
    in paper_ids.
    """
    paper_idx_to_date = {}
    pubmed_ids = [x for x in paper_ids if "PMC" not in x]
    #Break our queries into chunks of length 250.
    for chunk in chunk_list(pubmed_ids):
        paper_idx_to_date.update(PMIDsToYear(chunk))
    
    pmc_ids = [x for x in paper_ids if "PMC" in x]
    for chunk in chunk_list(pmc_ids):
        paper_idx_to_date.update(PMCIDsToYear(chunk))
    return paper_idx_to_date

def calculate_recency(known, response,verbose=False):
    """
    Calculate the recency of each chemical in the response.
    Look on the known edge, and find the earliest support for the edge using the TM PMID API
    see
     https://github.com/UCDenver-ccp/DocumentMetadataAPI/blob/main/README.md
     
    The general flow of this code is as follows. 
    1) Parse the TRAPI and find the relevant disease curies and list of drug curies from the response.
    2) Normalize the list of drug curies.
    3) Go to the ROBOKOPKG, ask it specifically for the TextMineKP edges between the Disease and Drug nodes.
    4) Go to Pubmed, get the year of publication for every paper we found in step 3.
    5) Break the results up into each drug-disease pair, and report them back.
    
    Step 3 and 4 are complicated by two factors. One is that it is substantially easier to query ROBOKOPKG and
    the Pubmed API with bulk queries then individually. It would produce a better logical flow of the code to
    go through every individual disease-drug pair, send a query to ROBOKOP to get a list of publications, then send
    a query to Pubmed asking for the year each publication was published. Unfortunately, that takes prohibitively 
    long to run. The second issue is normalization of drugs; I don't want to drop any identifier information, so part 
    of the code is juggling the unnormalized and normalized drug identifiers.

    """
    #Get the drug identifier from the TRAPI Query.
    disease_idx = getQueryNode(response)[0]
    if(verbose):print("We found this TRAPI had disease identifier:",disease_idx)
    #Get the list of all drug identifiers from the TRAPI query. This list
    # is not necessarily normalized to the specifications of node normalizer.
    unnormalized_drug_list = list(drug_idx_generator(response))
    if(verbose):print("We found this TRAPI had the following numbers of drug identifers:",len(unnormalized_drug_list))
    #Go to ROBOKOPKG, query each disease-drug pair; find those with an edge from TextMiningKP.
    # For those pairs with edges from TextMiningKP, return those publications as both a dictionary
    # and as a large set of all identifiers we came across (we need this set of all identifiers
    # to make querying Pubmed simplier in our next step).
    pubs_for_pairs, all_pubs = getPublistForPairs(disease_idx,unnormalized_drug_list)
    if(verbose):print("We found this TRAPI had the following numbers of publications from TextMiningKP:",len(all_pubs))

    # Generate a dictonary for the earliest year of publication for each paper 
    # identifer we found in our ROBOKOP query.
    pub_to_date = getDatesFromPaperIdentifiers(all_pubs)
    if(verbose):print("We have finished querying Pubmed and PubmedCentral for publication dates.")
    recency = {}
    
    for drug_idx in unnormalized_drug_list:        
        pub_list = pubs_for_pairs[(disease_idx,drug_idx)]
        if(len(pub_list)!=0): earliest_year = min([pub_to_date[paper_idx] for paper_idx in pub_list])
        else: earliest_year = None
        if(verbose):
            print(disease_idx,drug_idx)
            print("List of pubs",pub_list)
            print(earliest_year)
            print("----------")
        recency[drug_idx] = earliest_year
        
    return recency