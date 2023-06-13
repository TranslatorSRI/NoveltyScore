from rdkit import Chem
from rdkit import DataStructs
from rdkit.Chem import AllChem
import requests as rq
from contextlib import closing
import pubchempy as pcp

"""
    for each chemical in the unknowns, calculate the minimum nearest neighbor distance
    between it and the chemicals in the known.  If they're not in the response already, NN will give
    inchikeys.
"""

#TODO Develop an alternate workflow for finding SMILES when MolePro may fail to find them.
#Perhaps use Chemical Identifier resolver (CIR) to solve this. (https://cactus.nci.nih.gov/chemical/structure)

# First, get INCHI keys from node normalizer.
def getNodeNormINCHIKEYS(curie_ids):
    nodenorm_url = f"https://nodenormalization-sri.renci.org/1.3/get_normalized_nodes?&conflate=true"
    nodenorm_response  = rq.post(nodenorm_url, json={'curies':curie_ids})
    response_json = nodenorm_response.json()

    all_chemical_curies = {}
    for orig_curie,id_dict in response_json.items():
        all_curies = []
        if id_dict:
            for i in id_dict['equivalent_identifiers']:
                if "INCHIKEY" in i['identifier']:
                    #print(i['identifier'])
                    all_curies.append(i['identifier'])
            all_curies = list(set(all_curies))# remove all duplicate CURIEs from list
            all_chemical_curies[orig_curie] = all_curies
    #print(all_chemical_curies)
    return all_chemical_curies

# Next, take those INCHIKEYs and get SMILES from MolePro
def getMoleProINCHIKEYtoSMILES(all_chemical_curies):
    curies = list(all_chemical_curies.keys())
    inchikeys = [value[0].replace('INCHIKEY:','') for key,value in all_chemical_curies.items()]
    i=0
    for inchikey in inchikeys:
        base_url = 'https://molepro.broadinstitute.org/molecular_data_provider/'
        with closing(rq.post(base_url+'element/by_name', json=[inchikey])) as response_obj1:
            response1 = response_obj1.json()
            if 'id' in response1 and response1['id'] is not None:
                with closing(rq.get(base_url+'collection/'+response1['id']+'?cache=no')) as response_obj2:
                    response2 = response_obj2.json()
                    if 'elements' in response2 and response2['elements'] is not None:
                        if response2['elements'] == []:
                            print('Failed to find SMILES for',curies[i])
                            all_chemical_curies[curies[i]]="No SMILES could be found"
                            i+=1
                            continue
                        for element in response2['elements']:
                            smiles = element['identifiers'].get('smiles')
                            if smiles is not None:
                                all_chemical_curies[curies[i]]=smiles
                            else:
                                print('Failed to find SMILES for',curies[i])
                                all_chemical_curies[curies[i]]="No SMILES could be found"
                        i+=1

    return all_chemical_curies

import pubchempy as pcp

#Backup function to retrieve SMILES from a PUBCHEM.COMPOUND curie in the eq. identifiers field.
def getPubChemSMILES(pubchem_id):
    pubchem_id = pubchem_id.replace("PUBCHEM.COMPOUND:","")
    try:
        compound = pcp.get_compounds(pubchem_id)[0]
        return compound.canonical_smiles
    except (IndexError, pcp.PubChemHTTPError) as e:
        print(f"Error retrieving SMILES for PubChem ID {pubchem_id}: {e}")
        return None

# To use this function, you need to provide the following parameters:

#     unknown_smiles_dict: A dictionary of unknown (non-lookup) chemical CURIES and their SMILES
#     known_smiles_dict: A dictionary of known (found in lookup) chemical CURIES and their SMILES
#     similarity_cutoff: The minimum similarity score required to consider a molecule as a nearest neighbor.
#     num_neighbors: The maximum number of nearest neighbors to retrieve.

def find_nearest_neighbors(unknown_smiles_dict, known_smiles_dict, similarity_cutoff, num_neighbors):
    # Get list of smiles for both known and unknown CURIES
    unknown_smiles = {key:value for key,value in unknown_smiles_dict.items() if value != "No SMILES could be found"}
    print(unknown_smiles)
    known_smiles = {key:value for key,value in known_smiles_dict.items() if value != "No SMILES could be found"}
    print(known_smiles)

    # Convert input SMILES to a molecule
    known_mols = {}
    for key,value in known_smiles.items():
        known_mol = Chem.MolFromSmiles(value)
        if known_mol is None:
            raise ValueError("Invalid SMILES string for",key)
        else:
            known_mols.update({key:known_mol})
    nearest_neighbor_mapping = {}
    for unknownkey,value in unknown_smiles.items():
        query_mol = Chem.MolFromSmiles(value)
        if query_mol is None:
            raise ValueError("Invalid SMILES string")

        # Calculate fingerprints for the query molecule
        query_fp = AllChem.GetMorganFingerprint(query_mol, 2)

        # Calculate similarity scores between the query molecule and all molecules in the dataset
        similarities = []
        for key, mol in known_mols.items():
            fp = AllChem.GetMorganFingerprint(mol, 2)
            similarity = DataStructs.TanimotoSimilarity(query_fp, fp)
            similarities.append((key, similarity))

        # Sort the similarities in descending order
        similarities.sort(key=lambda x: x[1], reverse=True)

        # Retrieve the nearest neighbors
        neighbors = []
        for i in range(min(num_neighbors, len(similarities))):
            index, similarity = similarities[i]
            if similarity >= similarity_cutoff:
                neighbors.append((index, similarity))
        nearest_neighbor_mapping.update({unknownkey:neighbors})
    return nearest_neighbor_mapping

# Here's an example usage of these functions:
unknown_curies = ["PUBCHEM.COMPOUND:2519"] #Caffeine
known_curies = ["PUBCHEM.COMPOUND:2244","PUBCHEM.COMPOUND:3032732","PUBCHEM.COMPOUND:5429"] #3032732 should fail, as an example
curie_ids = unknown_curies + known_curies
inchikey_dict = getNodeNormINCHIKEYS(curie_ids)
print(inchikey_dict)

smiles_dict = getMoleProINCHIKEYtoSMILES(inchikey_dict)
print(smiles_dict)

for compound in smiles_dict.keys():
    check_smiles = smiles_dict[compound]
    if check_smiles == 'No SMILES could be found':
        if "PUBCHEM.COMPOUND:" in compound:
            try:
                pubchem_smiles = getPubChemSMILES(compound)
                smiles_dict[compound] = pubchem_smiles
            except:
                continue


unknown_smiles_dict = {key:smiles_dict[key] for key in unknown_curies}
known_smiles_dict = {key:smiles_dict[key] for key in known_curies}
nearest_neighbors = find_nearest_neighbors(unknown_smiles_dict, known_smiles_dict, 0, 3)
print(nearest_neighbors) #Should show that theobromine (5429) is most similar to caffeine.

