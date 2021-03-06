import sys
import warnings
from utils import getGloveWordmap
from params import params
from utils import Get_Ner_bioes_and_Char
from utils import getTagger
from utils import getTaggerlist

import random
import numpy as np
import theano

random.seed(1)
np.random.seed(1)

warnings.filterwarnings("ignore")
params = params()

def Base(eta, l3, emb, num_filters, inf, hidden_inf):
	params.outfile = 'CRF_Inf_NER_'
	params.dataf = '../ner_data/eng.train.bioes.conll'
        params.dev = '../ner_data/eng.dev.bioes.conll'
        params.test = '../ner_data/eng.test.bioes.conll'
	
	params.batchsize = 10
        params.hidden = 200
        params.embedsize = 100
        params.emb = emb
        params.eta = eta
        params.dropout = 1
	params.hidden_inf = hidden_inf

        params.char_embedd_dim = 30
        params.num_filters = num_filters


        params.inf = inf
        params.regutype = 0
        params.annealing = 1
        params.L3 = l3
	

	(words, We) = getGloveWordmap('../embedding/glove.6B.100d.txt')
	words.update({'UUUNKKK':0})
	a=[0]*len(We[0])
	newWe = []
	newWe.append(a)
	We = newWe + We
	We = np.asarray(We).astype('float32')
	tagger = getTagger('../ner_data/ner_bioes')
	params.taggerlist = getTaggerlist('../ner_data/ner_bioes')	

        char_dic = getTagger('../ner_data/char_dic')
        params.char_dic = char_dic

        scale = np.sqrt(3.0 / params.char_embedd_dim)
        char_embedd_table = np.random.uniform(-scale, scale, [len(char_dic), params.char_embedd_dim]).astype(theano.config.floatX)
 
	params.words = words
	params.tagger = tagger
       
	params.outfile = params.outfile+".num_filters"+'_'+str(num_filters)+'_dropout_'+ str(params.dropout) + '_LearningRate_'+str(params.eta)+ '_'  + str(l3) +'_emb_'+ str(emb)+ '_inf_'+ str(params.inf)+ '_hidden_'+ str(params.hidden_inf) + '_annealing_'+ str(params.annealing)
	

        trainx0, trainx0_char, trainy0, _ , _ = Get_Ner_bioes_and_Char(params.dataf, words, tagger, char_dic)
        train = trainx0, trainy0, trainx0_char

        devx0, devx0_char, devy0, params.devrawx, params.devpos = Get_Ner_bioes_and_Char(params.dev, words, tagger, char_dic)
        dev = devx0, devy0, devx0_char
        
        testx0, testx0_char, testy0, params.testrawx, params.testpos  = Get_Ner_bioes_and_Char(params.test, words, tagger, char_dic)
        test = testx0, testy0, testx0_char


	
	if (inf ==0) or (inf==1):
		from model_selection_NER_inference import CRF_model
		tm = CRF_model(We, char_embedd_table, params)
		tm.train(train, dev, test, params)

	elif(inf==2):
		from model_selection_inference_NER_seq2seq import CRF_seq2seq_model
		params.de_hidden_size = hidden_inf
		#params.outfile = 'de_hidden_' + str(params.de_hidden_size) + '_' + params.outfile
		tm = CRF_seq2seq_model(We, char_embedd_table, params)
                tm.train(train, dev, test, params)

	else:
                from model_selection_inference_NER_seq2seq_beamsearch import CRF_seq2seq_model
                params.de_hidden_size = hidden_inf
                #params.outfile = 'de_hidden_' + str(params.de_hidden_size) + '_' + params.outfile
                tm = CRF_seq2seq_model(We, char_embedd_table, params)
                tm.train(train, dev, test, params)

if __name__ == "__main__":
	Base(float(sys.argv[1]), float(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]))
