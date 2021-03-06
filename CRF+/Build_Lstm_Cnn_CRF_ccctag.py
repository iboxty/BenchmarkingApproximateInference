import numpy as np
from params import params
import theano
from theano import tensor as T
import lasagne
import random as random
import pickle
import cPickle
import time
import sys
from lasagne_embedding_layer_2 import lasagne_embedding_layer_2
from random import randint

from crf_utils import crf_loss0, crf_accuracy0






random.seed(1)
np.random.seed(1)
eps = 0.0000001


def saveParams(para, fname):
        f = file(fname, 'wb')
        cPickle.dump(para, f, protocol=cPickle.HIGHEST_PROTOCOL)
        f.close()


def get_minibatches_idx(n, minibatch_size, shuffle=False):
        idx_list = np.arange(n, dtype="int32")

        if shuffle:
            np.random.shuffle(idx_list)

        minibatches = []
        minibatch_start = 0
        for i in range(n // minibatch_size):
            minibatches.append(idx_list[minibatch_start:
                                    minibatch_start + minibatch_size])
            minibatch_start += minibatch_size

        if (minibatch_start != n):
            # Make a minibatch out of what is left
            minibatches.append(idx_list[minibatch_start:])

        return zip(range(len(minibatches)), minibatches)



Max_Char_Length = 30
class CRF_model(object):

	def prepare_data(self, seqs, labels, char_seqs):
		lengths = [len(s) for s in seqs]
                n_samples = len(seqs)
                maxlen = np.max(lengths)
                #sumlen = sum(lengths)

                x = np.zeros((n_samples, maxlen)).astype('int32')
                x_mask = np.zeros((n_samples, maxlen)).astype(theano.config.floatX)
                y = np.zeros((n_samples, maxlen)).astype('int32')
                char_x = np.zeros((n_samples, maxlen, Max_Char_Length)).astype('int32')

		x_mask1 = np.zeros((n_samples, maxlen)).astype(theano.config.floatX)
                for idx, s in enumerate(seqs):
                        x[idx,:lengths[idx]] = s
                        x_mask[idx,:lengths[idx]] = 1.
                        y[idx,:lengths[idx]] = labels[idx]
			x_mask1[idx,lengths[idx]-1] = 1.
                        for j in range(len(char_seqs[idx])):

                               char_length = len(char_seqs[idx][j])
                               char_x[idx, j, :char_length] = char_seqs[idx][j]

                return x, x_mask, char_x, x_mask1, y, maxlen
        

		

	def __init__(self,  We_initial, char_embedd_table_initial, params):
		self.textfile = open(params.outfile, 'w')
		We = theano.shared(We_initial)
        	embsize = We_initial.shape[1]
        	hidden = params.hidden

                char_embedd_dim = params.char_embedd_dim
                char_dic_size = len(params.char_dic)
                char_embedd_table = theano.shared(char_embedd_table_initial)

		trans = np.random.uniform(-0.01, 0.01, (params.num_labels +1, params.num_labels + 1)).astype('float32')
		transition = theano.shared(trans)


		input_var = T.imatrix(name='inputs')
        	target_var = T.imatrix(name='targets')
        	mask_var = T.fmatrix(name='masks')
		mask_var1 = T.fmatrix(name='masks1')
		length = T.iscalar()
                char_input_var = T.itensor3(name='char-inputs')


                l_in_word = lasagne.layers.InputLayer((None, None))
                l_mask_word = lasagne.layers.InputLayer(shape=(None, None))

		if params.emb ==1:
                        l_emb_word = lasagne.layers.EmbeddingLayer(l_in_word,  input_size= We_initial.shape[0] , output_size = embsize, W =We, name='word_embedding')
                else:
                        l_emb_word = lasagne_embedding_layer_2(l_in_word, embsize, We)


                layer_char_input = lasagne.layers.InputLayer(shape=(None, None, Max_Char_Length ),
                                                     input_var=char_input_var, name='char-input')

                layer_char = lasagne.layers.reshape(layer_char_input, (-1, [2]))
                layer_char_embedding = lasagne.layers.EmbeddingLayer(layer_char, input_size=char_dic_size,
                                                             output_size=char_embedd_dim, W=char_embedd_table,
                                                             name='char_embedding')

                layer_char = lasagne.layers.DimshuffleLayer(layer_char_embedding, pattern=(0, 2, 1))


                # first get some necessary dimensions or parameters
                conv_window = 3
                num_filters = params.num_filters
                #_, sent_length, _ = incoming2.output_shape

                # dropout before cnn?
                if params.dropout:
                     layer_char = lasagne.layers.DropoutLayer(layer_char, p=0.5)

                # construct convolution layer
                cnn_layer = lasagne.layers.Conv1DLayer(layer_char, num_filters=num_filters, filter_size=conv_window, pad='full',
                                           nonlinearity=lasagne.nonlinearities.tanh, name='cnn')
                # infer the pool size for pooling (pool size should go through all time step of cnn)
                _, _, pool_size = cnn_layer.output_shape
                print pool_size
                # construct max pool layer
                pool_layer = lasagne.layers.MaxPool1DLayer(cnn_layer, pool_size=pool_size)
                # reshape the layer to match lstm incoming layer [batch * sent_length, num_filters, 1] --> [batch, sent_length, num_filters]
                output_cnn_layer = lasagne.layers.reshape(pool_layer, (-1, length, [1]))

                # finally, concatenate the two incoming layers together.
                incoming = lasagne.layers.concat([output_cnn_layer, l_emb_word], axis=2)
                if params.dropout:
                     incoming = lasagne.layers.DropoutLayer(incoming, p=0.5)

		l_lstm_wordf = lasagne.layers.LSTMLayer(incoming, hidden, mask_input=l_mask_word, grad_clipping=5.)
        	l_lstm_wordb = lasagne.layers.LSTMLayer(incoming, hidden, mask_input=l_mask_word, grad_clipping=5., backwards = True)


               

        	concat = lasagne.layers.concat([l_lstm_wordf, l_lstm_wordb], axis=2)
                
                if params.dropout:
                     concat = lasagne.layers.DropoutLayer(concat, p=0.5)	

	
		l_reshape_concat = lasagne.layers.ReshapeLayer(concat,(-1,2*hidden))

		l_local = lasagne.layers.DenseLayer(l_reshape_concat, num_units= params.num_labels, nonlinearity=lasagne.nonlinearities.linear)


        	#bi_lstm_crf = CRFLayer(concat, params.num_labels, mask_input= l_mask_word)


		local_energy = lasagne.layers.get_output(l_local, {l_in_word: input_var, l_mask_word: mask_var,  layer_char_input:char_input_var})
		local_energy = local_energy.reshape((-1, length, params.num_labels))
                local_energy = local_energy*mask_var[:,:,None]		

		end_term = transition[:-1,-1]
		local_energy = local_energy + end_term.dimshuffle('x', 'x', 0)*mask_var1[:,:, None]

		local_energy_eval = lasagne.layers.get_output(l_local, {l_in_word: input_var, l_mask_word: mask_var, layer_char_input:char_input_var}, deterministic=True)
                local_energy_eval = local_energy_eval.reshape((-1, length, params.num_labels))
                local_energy_eval = local_energy_eval*mask_var[:,:,None]
                local_energy_eval = local_energy_eval + end_term.dimshuffle('x', 'x', 0)*mask_var1[:,:, None]	
	

 		length_index = T.sum(mask_var, axis=1)   

        	loss_train = crf_loss0(local_energy,  transition, target_var, mask_var).mean()
		#loss_train = T.dot(loss_train, length_index)/T.sum(length_index)

		#loss_train = crf_loss0(local_energy, transition, target_var, mask_var).mean()

        	prediction, corr = crf_accuracy0(local_energy_eval, transition, target_var, mask_var)

		##loss_train = crf_loss(energies_train, target_var, mask_var).mean()

                ##prediction, corr = crf_accuracy(energies_train, target_var)


        	corr_train = (corr * mask_var).sum(dtype=theano.config.floatX)
        	num_tokens = mask_var.sum(dtype=theano.config.floatX)



        	network_params = lasagne.layers.get_all_params(l_local, trainable=True)
		network_params.append(transition)

        	print network_params
		self.network_params = network_params

		loss_train = loss_train + params.L2*sum(lasagne.regularization.l2(x) for x in network_params)

        	updates = lasagne.updates.sgd(loss_train, network_params, params.eta)
                updates = lasagne.updates.apply_momentum(updates, network_params, momentum=0.9)

        	self.train_fn = theano.function([input_var, char_input_var, target_var, mask_var, mask_var1, length], loss_train, updates=updates, on_unused_input='ignore')

        	self.eval_fn = theano.function([input_var, char_input_var, target_var, mask_var, mask_var1, length], [corr_train, num_tokens, prediction], on_unused_input='ignore')




                						

		
	def train(self, train, dev, test, params):	
		
                trainX, trainY, trainChar = train
                devX, devY, devChar = dev
                testX, testY, testChar = test

		#trainx0, trainx0mask, trainx0mask1, trainy0, trainmaxlen = self.prepare_data(trainX, trainY)
		#devx0, devx0mask, devx0_char, devx0mask1, devy0, devmaxlen = self.prepare_data(devX, devY, devChar)
		#testx0, testx0mask, testx0_char, testx0mask1, testy0, testmaxlen = self.prepare_data(testX, testY, testChar)
	
           

        	bestdev = -1

        	bestdev_time =0
        	counter = 0
        	try:
            		for eidx in xrange(30):
                		n_samples = 0

                		start_time1 = time.time()
                		kf = get_minibatches_idx(len(trainX), params.batchsize, shuffle=True)
                		uidx = 0
		
				
                		for _, train_index in kf:

                    			uidx += 1

                    			x0 = [trainX[ii] for ii in train_index]
                    			y0 = [trainY[ii] for ii in train_index]
                                        charx0 = [trainChar[ii] for ii in train_index]
                    			n_samples += len(train_index)
					#print y0
					x0, x0mask, x0_char, x0mask1, y0, maxlen = self.prepare_data(x0, y0, charx0)					
					#start_time = time.time()
                 			cost = self.train_fn(x0, x0_char, y0, x0mask, x0mask1 , maxlen)
					#end_time = time.time()
			
				
				self.textfile.write("Seen samples:%d   \n" %( n_samples)  )
				self.textfile.flush()
		
				end_time1 = time.time()
				bestdev0 = 0
				best_t0 = 0
				bestdev0_0 = 0
                                best_t1 = 0

								
				#start_time = time.time()
				#_, testpred0, testnum0, _   = self.eval_fn(testx0, testy0, testx0mask, testx0mask1,testmaxlen)

				#end_time = time.time()
                                #print('inference', end_time-start_time)
				
				#trainloss, trainpred, trainnum,_    = self.eval_fn(trainx0, trainy0, trainx0mask,trainx0mask1 ,trainmaxlen)
				start_time = time.time()
				dev_kf = get_minibatches_idx(len(devX), 100)
				devpred = 0
				devnum = 0
				for _, dev_index in dev_kf:
					devX0 = [devX[ii] for ii in dev_index]
                                        devY0 = [devY[ii] for ii in dev_index]
                                        devX0_char = [devChar[ii] for ii in dev_index]
					devx0, devx0mask, devx0_char, devx0mask1, devy0, devmaxlen = self.prepare_data(devX0, devY0, devX0_char)
					devpred0, devnum0, _   = self.eval_fn(devx0, devx0_char, devy0, devx0mask, devx0mask1, devmaxlen)
					devpred += devpred0
					devnum += devnum0
				devacc = 1.0*devpred/devnum
				end_time = time.time()
				#print('inference', end_time-start_time)
				
				
				if bestdev < devacc:
                                        bestdev = devacc
                                        best_t = eidx
                                        test_kf = get_minibatches_idx(len(testX), 100)
                                        testpred = 0
                                        testnum = 0
                                        for _, test_index in test_kf:
                                               testX0 = [testX[ii] for ii in test_index]
                                               testY0 = [testY[ii] for ii in test_index]
                                               testX0_char = [testChar[ii] for ii in test_index]
                                               testx0, testx0mask, testx0_char, testx0mask1, testy0, testmaxlen = self.prepare_data(testX0, testY0, testX0_char)
                                               testpred0, testnum0, _   = self.eval_fn(testx0, testx0_char, testy0, testx0mask, testx0mask1, testmaxlen)
                                               testpred += testpred0
                                               testnum += testnum0
                                        testacc = 1.0*testpred/testnum
                                        #para = [p.get_value() for p in self.network_params]
                                        #saveParams(para , params.outfile+ '.pickle')
				
                                self.textfile.write("epoches %d  devacc %f  testacc %f trainig time %f test time %f \n" %( eidx + 1, devacc, testacc, end_time1 - start_time1, end_time - start_time ) )
                                self.textfile.flush()
				
			       
        	except KeyboardInterrupt:
            		#print "Classifer Training interupted"
            		self.textfile.write( 'classifer training interrupt \n')
			self.textfile.flush()
        	end_time = time.time()
		#self.textfile.write("total time %f \n" % (end_time - start_time))
		self.textfile.write("best dev acc: %f  at time %d \n" % (bestdev, best_t))
		print 'bestdev ', bestdev, 'at time ',best_t
        	self.textfile.close()
		
