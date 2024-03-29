import data_utils as du
import torch
import gzip
import tqdm
import torch.utils.data as data
import random

MAX_QCOUNT = 20
size = 0

def pad(arr, l):
    while len(arr) < l:
            arr.append(0)

def padmask(origlen, maxlen):
    m = []

    for i in range(maxlen):
        if i < origlen:
            m.append(1)
        else:
            m.append(0)
    return m

def evalSampleDic(q_title, q_body, qt_mask, qb_mask):
    sample = {
    'titles': [q_title],
    'bodies':[q_body],
    'titles_masks':[qt_mask],
    'bodies_masks':[qb_mask],
    'similar':[]
    }
    return sample

def trainSampleDic(q_title, p_title, q_body, p_body, qt_mask, pt_mask, qb_mask, pb_mask):
    sample = {
    'titles': [q_title, p_title],
    'bodies':[q_body, p_body],
    'titles_masks':[qt_mask, pt_mask],
    'bodies_masks':[qb_mask, pb_mask]
    }
    return sample

def processCandidate(sample, candidate, id2data, max_title, max_body):
    (title, t_mask), (body, b_mask) = id2data[candidate]

    t_mask = padmask(t_mask, max_title)
    b_mask = padmask(b_mask, max_body)

    pad(title, max_title)
    pad(body, max_body)

    sample['titles'].append(title)
    sample['bodies'].append(body)
    sample['titles_masks'].append(t_mask)
    sample['bodies_masks'].append(b_mask)

def getCandidate(uset, id2data_list):
    while True:
        candidate = random.choice(id2data_list)
        if candidate not in uset:
            break
    return candidate

def fillInTrainSample(sample, p, q, negs, pos, id2data, id2data_list, max_title, max_body):
    count_negs = 0

    while count_negs < MAX_QCOUNT-1:
        neg_candidate = None
        if count_negs < len(negs):
            neg_candidate = negs[count_negs]
        if count_negs >= len(negs) or neg_candidate not in id2data:
            neg_candidate = getCandidate(set().union(negs, pos, [q]), id2data_list)

        processCandidate(sample, neg_candidate, id2data, max_title, max_body)
        count_negs += 1

def fillInEvalSample(sample, query_q, rest_qs, pos, id2data, id2data_list, max_title, max_body):

    for i, item in enumerate(rest_qs):
        if item in pos:
            sample['similar'].append(i)
        processCandidate(sample, item, id2data, max_title, max_body)

    if len(sample['similar']) < MAX_QCOUNT:
        while len(sample['similar']) < MAX_QCOUNT:
            sample['similar'].append(-1)

class AskUbuntuDataset(data.Dataset):
    def __init__(self, path, id2data, max_title, max_body, isTrain):
        self.path = path
        self.dataset = []
        self.id2data = id2data
        self.title_dim = max_title
        self.body_dim = max_body
        self.id2data_list = list(id2data)

        with open(path) as f:
            for line in tqdm.tqdm(f):
                split = line.split('\t')
                q = split[0]
                pos = split[1].split()
                rest_q = split[2].split()

                if isTrain:
                    negs = [x for x in rest_q if x not in pos]

                    for p in pos:
                        sample = self.createSample(q, p, negs, pos, max_title, max_body, isTrain)
                        if sample != None:
                            self.dataset.append(sample)
                else:
                    if len(pos) > 0:
                        sample = self.createSample(q, -1, rest_q, pos, max_title, max_body, isTrain)
                    if sample != None:
                        self.dataset.append(sample)


    def createSample(self, q, p, rest_qs, pos, max_title, max_body, isTrain):
        if q not in self.id2data or (p not in self.id2data and p != -1):
            return None

        (q_title, qt_mask), (q_body, qb_mask) = self.id2data[q]
        qt_mask = padmask(qt_mask, max_title)
        qb_mask = padmask(qb_mask, max_body)
        pad(q_title, max_title)
        pad(q_body, max_body)

        if isTrain:
            (p_title, pt_mask), (p_body, pb_mask) = self.id2data[p]
            pt_mask = padmask(pt_mask, max_title)
            pb_mask = padmask(pb_mask, max_body)
            pad(p_title, max_title)
            pad(p_body, max_body)
            sample = trainSampleDic(q_title, p_title, q_body, p_body, qt_mask, pt_mask, qb_mask, pb_mask)
        else:
            sample = evalSampleDic(q_title, q_body, qt_mask, qb_mask)

        random.shuffle(rest_qs)

        if isTrain == False:
            random.shuffle(pos)
            fillInEvalSample(sample, q, rest_qs, pos, self.id2data, self.id2data_list, max_title, max_body)
        else:
            fillInTrainSample(sample, p, q, rest_qs, pos, self.id2data, self.id2data_list, max_title, max_body)

        for key in sample:
            sample[key] = torch.LongTensor(sample[key])

        return sample

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self,index):
        sample = self.dataset[index]
        return sample
