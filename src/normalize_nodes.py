import requests
import time
import csv
import sys
import pandas as pd

def post_query(url, query_dict):
    try:
        resp = requests.post(url,json=query_dict,timeout=600)
    except requests.exceptions.ReadTimeout:
        print("Request timed out!")
        logging.warning("Request timed out!")
        return "Error",-1
    except requests.exceptions.ConnectionError:
        print("Request had connection error")
        logging.warning("Request had connection error!")
        return "Error",-1
    #print("Query is posted")
    if resp.status_code != 200:
        raise ValueError("Node normalizer sent", resp.status_code)
        #return "Error",resp.status_code

    return resp

def normalize_data_frame(df, key, idx_col=None, name_col=None):
    if(idx_col==None): idx_col = key+"_normalized_idx"
    if(name_col==None): name_col = key+"_normalized_name"
    cols = df.columns.tolist()
    if(key not in cols): raise ValueError(f"{key} is not in the provided dataframe")
    cols.insert(cols.index(key)+1, name_col)
    cols.insert(cols.index(key)+1, idx_col)

    normalize_map = normalize_big_list(list(df[key].unique()))
    #The dictonary should have a result (identifier, name) if it was able to be normalized.
    #This lambda basically goes and gets either the identifer or name for the dictonary we generated.
    def lambdaFunc(row,index, key):
        drug = normalize_map[row[key]]
        if(drug==None):return None
        else: return drug[index]

    df[idx_col] = df.apply(lambdaFunc,index=0, key=key, axis=1)
    df[name_col] = df.apply(lambdaFunc,index=1, key=key, axis=1)

    #Return the dataframe with the columns reordered to be (col_1, col_2, KEY, key_normalized_idx, key_normalized_name, col_4,..)
    return df[cols]



def normalize_list(l):
    d = {"curies": l}
    URL="https://nodenormalization-sri.renci.org/1.3/get_normalized_nodes"
    x = post_query(URL,d)
    #print(x)
    j = x.json()
#    "id": {
#      "identifier": "PUBCHEM.COMPOUND:962",
#      "label": "Water"
    result_d = {}
    for k in j.keys():
        if(j[k]==None):continue
        idx = j[k]['id']['identifier']
        label = j[k]['id'].get('label',"")
#        results.append((k,idx,label))
        result_d[k] = (idx,label)
    return result_d
 


def divide_chunks(l, n):
    # looping till length l
    for i in range(0, len(l), n):
        yield l[i:i + n]

def normalize_big_list(l, pbar=None):
    normalized_dict = {}
    cnt = 0
    if(type(pbar)!=type(None)):pbar.total = len(l)//100
        
    for chunk in divide_chunks(l,100):
        cnt+=1
        d = normalize_list(chunk)
        for val in chunk:
            idx_and_label_tuple = d.get(val,None)
            normalized_dict[val] = idx_and_label_tuple
        if(type(pbar)!=type(None)):pbar.update(1)
    return normalized_dict
       

if(__name__=="__main__"):
    l = [ "MESH:D014867", "NCIT:C34373"]
    a = normalize_list(l)
    print(a)
    exit()

    fname = sys.argv[1]
    out_fname = sys.argv[2]
    vals = []
    with open(fname) as f:
        for line in f:
            vals.append(line.strip())

    with open(out_fname,'w') as f:
        cnt = 0
        writer = csv.writer(f)
        for chunk in divide_chunks(vals,100):
            cnt+=1
            d = normalize_list(chunk)
            print(cnt)
            for val in chunk:
                (idx,label) = d.get(val,("",''))
    #            f.write(f"{val},{idx},{label}\n") 
                writer.writerow([val,idx,label])
            time.sleep(0.1)
