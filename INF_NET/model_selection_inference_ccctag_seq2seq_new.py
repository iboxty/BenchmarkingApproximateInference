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

from crf import CRFLayer
from crf_utils import crf_loss0, crf_accuracy0






random.seed(1)
np.random.seed(1)
eps = 0.0000001
#eps = 1e-20

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


def init_xavier_uniform(n_in, n_out):
        import math
        a = math.sqrt(2.0/(n_in + n_out))
        W = np.random.uniform( -a, a,  (n_in, n_out)).astype(theano.config.floatX)
        return W


from LSTM_Layer import LSTM


class CRF_seq2seq_model(object):

	def prepare_data(self, seqs, labels):
		lengths = [len(s) for s in seqs]
                n_samples = len(seqs)
                maxlen = np.max(lengths)
                #sumlen = sum(lengths)

                x = np.zeros((n_samples, maxlen)).astype('int32')
                x_mask = np.zeros((n_samples, maxlen)).astype(theano.config.floatX)
		x_mask1 = np.zeros((n_samples, maxlen)).astype(theano.config.floatX)
                y = np.zeros((n_samples, maxlen)).astype('int32')
                for idx, s in enumerate(seqs):
                        x[idx,:lengths[idx]] = s
                        x_mask[idx,:lengths[idx]] = 1.
                        y[idx,:lengths[idx]] = labels[idx]
			x_mask1[idx,lengths[idx]-1] = 1.

                return x, x_mask, x_mask1, y, maxlen
        

		

	def __init__(self,  We_initial, params):
		self.textfile = open(params.outfile, 'w')
		We = theano.shared(We_initial)
        	embsize = We_initial.shape[1]
        	hidden = params.hidden

		self.num_labels = params.num_labels
		self.de_hidden_size = params.de_hidden_size
		self.en_hidden_size = params.en_hidden_size

		self.lstm_layers_num = 1		

		input_var = T.imatrix(name='inputs')
        	target_var = T.imatrix(name='targets')
		target_var_in = T.imatrix(name='in_targets')
        	mask_var = T.fmatrix(name='masks')
		mask_var1 = T.fmatrix(name='masks1')
		length = T.iscalar()
		length0 = T.iscalar()
		t_t = T.fscalar()
		t_t0 = T.fscalar()		

		Wyy0 = np.random.uniform(-0.02, 0.02, (self.num_labels + 1, self.num_labels + 1)).astype('float32')
                Wyy = theano.shared(Wyy0)


                l_in_word = lasagne.layers.InputLayer((None, None))
                l_mask_word = lasagne.layers.InputLayer(shape=(None, None))

		if params.emb ==1:
                        l_emb_word = lasagne.layers.EmbeddingLayer(l_in_word,  input_size= We_initial.shape[0] , output_size = embsize, W =We)
                else:
                        l_emb_word = lasagne_embedding_layer_2(l_in_word, embsize, We)


		l_lstm_wordf = lasagne.layers.LSTMLayer(l_emb_word, 512, mask_input=l_mask_word)
        	l_lstm_wordb = lasagne.layers.LSTMLayer(l_emb_word, 512, mask_input=l_mask_word, backwards = True)

        	concat = lasagne.layers.concat([l_lstm_wordf, l_lstm_wordb], axis=2)
		
		l_reshape_concat = lasagne.layers.ReshapeLayer(concat,(-1,2*512))

		l_local = lasagne.layers.DenseLayer(l_reshape_concat, num_units= self.num_labels, nonlinearity=lasagne.nonlinearities.linear)

		
		network_params = lasagne.layers.get_all_params(l_local, trainable=True)
                network_params.append(Wyy)

		
		print len(network_params)
		f = open('ccctag_CRF_Bilstm_Viterbi_.Batchsize_10_dropout_0_LearningRate_0.01_0.0512_tagversoin_2.pickle','r')
		data = pickle.load(f)
		f.close()

		for idx, p in enumerate(network_params):

                        p.set_value(data[idx])


		self.params = []
		self.hos = []
                self.Cos = []
		self.encoder_lstm_layers = []
                self.decoder_lstm_layers = []

		ei, di, dt = T.imatrices(3)    #place holders
                decoderInputs0 ,em, em1, dm, tf, di0 =T.fmatrices(6)
		


		#### the last one is for the stary symbole
                self.de_lookuptable = theano.shared(name="Decoder LookUpTable", value=init_xavier_uniform(self.num_labels +1, self.de_hidden_size), borrow=True)

                self.linear = theano.shared(name="Linear", value = init_xavier_uniform(self.de_hidden_size + 2*self.en_hidden_size, self.num_labels), borrow= True)
		self.linear_bias = theano.shared(name="Hidden to Bias", value=np.asarray(np.random.randn(self.num_labels, )*0., dtype=theano.config.floatX), borrow=True)
                #self.hidden_decode = theano.shared(name="Hidden to Decode", value= init_xavier_uniform(2*hidden, self.de_hidden_size), borrow = True)


		#self.hidden_bias = theano.shared(
                #        name="Hidden to Bias",
                #        value=np.asarray(np.random.randn(self.de_hidden_size, )*0., dtype=theano.config.floatX) ,
                #        borrow=True
                #        )

		input_var_shuffle = input_var.dimshuffle(1, 0)
                mask_var_shuffle = mask_var.dimshuffle(1, 0)
                target_var_in_shuffle = target_var_in.dimshuffle(1,0)
                target_var_shuffle = target_var.dimshuffle(1,0)
		

		self.params += [self.linear , self.linear_bias, self.de_lookuptable]    #concatenate
		state_below = We[input_var_shuffle.flatten()].reshape((input_var_shuffle.shape[0], input_var_shuffle.shape[1], embsize))
		enclstm_f = LSTM(embsize, self.en_hidden_size)
                enclstm_b = LSTM(embsize, self.en_hidden_size, True)

                self.encoder_lstm_layers.append(enclstm_f)    #append
                self.encoder_lstm_layers.append(enclstm_b)    #append

                self.params += enclstm_f.params + enclstm_b.params   #concatenate

                hs_f, Cs_f = enclstm_f.forward(state_below, mask_var_shuffle)
                hs_b, Cs_b = enclstm_b.forward(state_below, mask_var_shuffle)

                hs = T.concatenate([hs_f, hs_b], axis=2)
                Cs = T.concatenate([Cs_f, Cs_b], axis=2)
                		
		hs0 = T.concatenate([hs_f[-1], hs_b[0]], axis=1)
                Cs0 = T.concatenate([Cs_f[-1], Cs_b[0]], axis=1)
                #self.hos += T.tanh(tensor.dot(hs0, self.hidden_decode) + self.hidden_bias),
                #self.Cos += T.tanh(tensor.dot(Cs0, self.hidden_decode) + self.hidden_bias),
                self.hos += T.alloc(np.asarray(0., dtype=theano.config.floatX), input_var_shuffle.shape[1], self.de_hidden_size),
                self.Cos += T.alloc(np.asarray(0., dtype=theano.config.floatX), input_var_shuffle.shape[1], self.de_hidden_size),

                Encoder = hs

			
		state_below = self.de_lookuptable[target_var_in_shuffle.flatten()].reshape((target_var_in_shuffle.shape[0], target_var_in_shuffle.shape[1], self.de_hidden_size))
                for i in range(self.lstm_layers_num):
                        declstm = LSTM(self.de_hidden_size, self.de_hidden_size)
                        self.decoder_lstm_layers += declstm,    #append
                        self.params += declstm.params    #concatenate
                        ho, Co = self.hos[i], self.Cos[i]
                        state_below, Cs = declstm.forward(state_below, mask_var_shuffle, ho, Co)


                decoder_lstm_outputs = T.concatenate([state_below, Encoder], axis=2)
                linear_outputs = T.dot(decoder_lstm_outputs, self.linear) + self.linear_bias[None, None, :]
                softmax_outputs, updates = theano.scan(
                        fn=lambda x: T.nnet.softmax(x),
                        sequences=[linear_outputs],
                        )

                def _NLL(pred, y, m):
                        return -m * T.log(pred[T.arange(input_var.shape[0]), y])
		

		def _step2(ctx_, state_, hs_, Cs_):
			hs, Cs = [], []
                        token_idxs = T.cast(state_.argmax(axis=-1), "int32" )
                        msk_ = T.fill( (T.zeros_like(token_idxs, dtype="float32")), 1)
                        msk_ = msk_.dimshuffle('x', 0)
                        state_below0 = self.de_lookuptable[token_idxs].reshape((1, ctx_.shape[0], self.de_hidden_size))
                        for i, lstm in enumerate(self.decoder_lstm_layers):
                                h, C = lstm.forward(state_below0, msk_, hs_[i], Cs_[i])    #mind msk
                                hs += h[-1],
                                Cs += C[-1],
                                state_below0 = h

                        hs, Cs = T.as_tensor_variable(hs), T.as_tensor_variable(Cs)
                        state_below0 = state_below0.reshape((ctx_.shape[0], self.de_hidden_size))
                        state_below0 = T.concatenate([ctx_, state_below0], axis =1)
                        newpred = T.dot(state_below0, self.linear) + self.linear_bias[None, :]
                        state_below = T.nnet.softmax(newpred)

                        ##### the beging symbole probablity is 0
                        extra_p = T.zeros_like(hs[:,:,0])
                        state_below = T.concatenate([state_below, extra_p.T], axis=1)

                        return state_below, hs, Cs
                        

		hs0, Cs0 = T.as_tensor_variable(self.hos, name="hs0"), T.as_tensor_variable(self.Cos, name="Cs0")
                train_outputs, _ = theano.scan(
                        fn=_step2,
			sequences = [Encoder],
                        outputs_info=[decoderInputs0, hs0, Cs0],
                        n_steps=input_var_shuffle.shape[0]
                        )

                predy = train_outputs[0].dimshuffle(1, 0 , 2)
		predy = predy[:,:,:-1]*mask_var[:,:,None]
		predy0 = predy.reshape((-1, self.num_labels))
          
 

	
		def inner_function( targets_one_step, mask_one_step,  prev_label, tg_energy):
                        """
                        :param targets_one_step: [batch_size, t]
                        :param prev_label: [batch_size, t]
                        :param tg_energy: [batch_size]
                        :return:
                        """                 
                        new_ta_energy = T.dot(prev_label, Wyy[:-1,:-1])
                        new_ta_energy_t = tg_energy + T.sum(new_ta_energy*targets_one_step, axis =1)
			tg_energy_t = T.switch(mask_one_step, new_ta_energy_t,  tg_energy)

                        return [targets_one_step, tg_energy_t]


		local_energy = lasagne.layers.get_output(l_local, {l_in_word: input_var, l_mask_word: mask_var})
		local_energy = local_energy.reshape((-1, length, self.num_labels))
                local_energy = local_energy*mask_var[:,:,None]		

		#####################
		# for the end symbole of a sequence
		####################

		end_term = Wyy[:-1,-1]
                local_energy = local_energy + end_term.dimshuffle('x', 'x', 0)*mask_var1[:,:, None]


		#predy0 = lasagne.layers.get_output(l_local_a, {l_in_word_a:input_var, l_mask_word_a:mask_var})

		predy_in = T.argmax(predy0, axis=1)
                A = T.extra_ops.to_one_hot(predy_in, self.num_labels)
                A = A.reshape((-1, length, self.num_labels))		

		#predy = predy0.reshape((-1, length, 25))
		#predy = predy*mask_var[:,:,None]

		
		targets_shuffled = predy.dimshuffle(1, 0, 2)
                target_time0 = targets_shuffled[0]
		
		masks_shuffled = mask_var.dimshuffle(1, 0)		 

                initial_energy0 = T.dot(target_time0, Wyy[-1,:-1])


                initials = [target_time0, initial_energy0]
                [ _, target_energies], _ = theano.scan(fn=inner_function, outputs_info=initials, sequences=[targets_shuffled[1:], masks_shuffled[1:]])
                cost11 = target_energies[-1] + T.sum(T.sum(local_energy*predy, axis=2)*mask_var, axis=1)

		
		# compute the ground-truth energy

		targets_shuffled0 = A.dimshuffle(1, 0, 2)
                target_time00 = targets_shuffled0[0]


                initial_energy00 = T.dot(target_time00, Wyy[-1,:-1])


                initials0 = [target_time00, initial_energy00]
                [ _, target_energies0], _ = theano.scan(fn=inner_function, outputs_info=initials0, sequences=[targets_shuffled0[1:], masks_shuffled[1:]])
                cost110 = target_energies0[-1] + T.sum(T.sum(local_energy*A, axis=2)*mask_var, axis=1)
		
		
		#predy_f =  predy.reshape((-1, 25))
		y_f = target_var.flatten()

	
		if (params.annealing ==0):
                        lamb = params.L3
                elif (params.annealing ==1):
                        lamb = params.L3* (1 - 0.01*t_t)


		if (params.regutype==0):
                        ce_hinge = lasagne.objectives.categorical_crossentropy(predy0 + eps, y_f)
                        ce_hinge = ce_hinge.reshape((-1, length))
                        ce_hinge = T.sum(ce_hinge* mask_var, axis=1)
			cost = T.mean(-cost11) + lamb*T.mean(ce_hinge)
                else:

                        entropy_term = - T.sum(predy0 * T.log(predy0 + eps), axis=1)
                        entropy_term = entropy_term.reshape((-1, length))
                        entropy_term = T.sum(entropy_term*mask_var, axis=1)
			cost = T.mean(-cost11) - lamb*T.mean(entropy_term)

		"""
		f = open('F0_simple.pickle')
                PARA = pickle.load(f)
                f.close()
                l2_term = sum(lasagne.regularization.l2(x-PARA[index]) for index, x in enumerate(a_params))


                cost = T.mean(-cost11) + params.L2*l2_term
		"""
                    

		#from adam import adam
                #updates_a = adam(cost, self.params, params.eta)	
				
		#updates_a = lasagne.updates.sgd(cost, self.params, params.eta)
                #updates_a = lasagne.updates.apply_momentum(updates_a, self.params, momentum=0.9)

		from momentum import momentum
                updates_a = momentum(cost, self.params, params.eta, momentum=0.9)

		if (params.regutype==0):
			self.train_fn = theano.function(
                        	inputs=[ei, dt, em, em1, length0, t_t0, di0],
                        	outputs=[cost, ce_hinge],
                        	updates=updates_a,
				on_unused_input='ignore',
                        	givens={input_var:ei, target_var:dt, mask_var:em, mask_var1:em1, length: length0, t_t: t_t0, decoderInputs0:di0}
                        	)
			#self.train_fn = theano.function([input_var, target_var, mask_var, mask_var1, length, t_t], [cost, ce_hinge], updates = updates_a, on_unused_input='ignore')
		else:
			
			self.train_fn = theano.function(
                                inputs=[ei, dt, em, em1, length0, t_t0, di0],
                                outputs=[cost, entropy_term],
                                updates=updates_a,
				on_unused_input='ignore',
                                givens={input_var:ei, target_var:dt, mask_var:em, mask_var1:em1, length: length0, t_t: t_t0, decoderInputs0:di0}
                                )
			#self.train_fn = theano.function([input_var, target_var, mask_var, mask_var1, length, t_t], [cost, entropy_term], updates = updates_a, on_unused_input='ignore')


		prediction = T.argmax(predy, axis=2)
		corr = T.eq(prediction, target_var)
        	corr_train = (corr * mask_var).sum(dtype=theano.config.floatX)
        	num_tokens = mask_var.sum(dtype=theano.config.floatX)

		self.eval_fn = theano.function(
                                inputs=[ei, dt, em, em1, length0, di0],
                                outputs=[cost11, cost110, corr_train, num_tokens, prediction],
				on_unused_input='ignore',
                                givens={input_var:ei, target_var:dt, mask_var:em, mask_var1:em1, length: length0, decoderInputs0:di0}
                                )        	

	


                						

		
	def train(self, trainX, trainY, devX, devY, testX, testY, params):	
		
		#trainx0, trainx0mask, trainy0, trainmaxlen = self.prepare_data(trainX, trainY)
		#devx0, devx0mask, devx0mask1, devy0, devmaxlen = self.prepare_data(devX, devY)
		#devx1_in2 = np.zeros((len(devX), self.num_labels+1), dtype = 'float32')
                #devx1_in2[:,-1] = 1.

		#testx0, testx0mask, testx0mask1, testy0, testmaxlen = self.prepare_data(testX, testY)
		#testx1_in2 = np.zeros((len(testX), self.num_labels+1), dtype = 'float32')
                #testx1_in2[:,-1] = 1.	

		start_time = time.time()
        	bestdev = -1
		
		tagger_keys = params.tagger.keys()
                tagger_values = params.tagger.values()

                words_keys = params.words.keys()
                words_values = params.words.values()
		
        	best_t =0
        	counter = 0
        	try:
            		for eidx in xrange(50):
                		n_samples = 0

                		start_time1 = time.time()
                		kf = get_minibatches_idx(len(trainX), params.batchsize, shuffle=True)
                		uidx = 0
				#aa = 0
				#bb = 0
                		for _, train_index in kf:

                    			uidx += 1

                    			x0 = [trainX[ii] for ii in train_index]
                    			y0 = [trainY[ii] for ii in train_index]
                    			n_samples += len(train_index)
					#print y0
					x0, x0mask, x0mask1, y0, maxlen = self.prepare_data(x0, y0)
					
					x1_in2 = np.zeros((len(train_index), self.num_labels+1), dtype = 'float32')
                                        x1_in2[:,-1] = 1.
				
                 			cost, regu_cost = self.train_fn(x0, y0, x0mask, x0mask1, maxlen, eidx, x1_in2)
					#print regu_cost
								
				
				self.textfile.write("Seen samples:%d   \n" %( n_samples)  )
				self.textfile.flush()
		
				end_time1 = time.time()

								
				
				start_time2 = time.time()
				
				#trainloss, trainpred, trainnum,_    = self.eval_fn(trainx0, trainy0, trainx0mask, trainmaxlen)
				dev_kf = get_minibatches_idx(len(devX), 50)
                                devpred = 0
                                devnum = 0
                                for _, dev_index in dev_kf:
                                        devX0 = [devX[ii] for ii in dev_index]
                                        devY0 = [devY[ii] for ii in dev_index]
                                        devx0, devx0mask, devx0mask1, devy0, devmaxlen = self.prepare_data(devX0, devY0)
					devx1_in2 = np.zeros((len(dev_index), self.num_labels+1), dtype = 'float32')
                			devx1_in2[:,-1] = 1.
                                        _, _, devpred0, devnum0, _   = self.eval_fn(devx0, devy0, devx0mask, devx0mask1, devmaxlen, devx1_in2)
                                        devpred += devpred0
                                        devnum += devnum0
                                devacc = 1.0*devpred/devnum
				
				devlength = [len(s) for s in devX]			
				testlength = [len(s) for s in testX]	
				#print devloss, testloss
				print  'devacc ', devacc
				
				end_time2 = time.time()
				if bestdev < devacc:
					bestdev = devacc
					best_t = eidx
					
					#testloss, _, testpred, testnum, test_pred = self.eval_fn(testx0, testy0, testx0mask, testx0mask1, testmaxlen, testx1_in2)
					

					test_kf = get_minibatches_idx(len(testX), 50)
                                	testpred = 0
                                	testnum = 0
                                	for _, test_index in test_kf:
                                        	testX0 = [testX[ii] for ii in test_index]
                                        	testY0 = [testY[ii] for ii in test_index]
                                        	testx0, testx0mask, testx0mask1, testy0, testmaxlen = self.prepare_data(testX0, testY0)
						testx1_in2 = np.zeros((len(test_index), self.num_labels+1), dtype = 'float32')
                				testx1_in2[:,-1] = 1.
                                        	_, _, testpred0, testnum0, _   = self.eval_fn(testx0, testy0, testx0mask, testx0mask1,testmaxlen, testx1_in2)
                                        	testpred += testpred0
                                        	testnum += testnum0
                                	testacc = 1.0*testpred/testnum

					print  'devacc ', devacc, 'testacc ', testacc
					#para = [p.get_value() for p in self.a_params]
					#saveParams(para , params.outfile+ '.pickle')
					"""
					f = open('QA_' + params.outfile, 'w')
                                        for i in range(testloss.shape[0]):
                                                tweet_i = testX[i]
                                                pred_i = test_pred[i].tolist()
                                                pred_i = pred_i[:testlength[i]]
                                                pred_i = [ tagger_keys[tagger_values.index(x)] for x in pred_i]
                                                pred_i = ' '.join(str(x) for x in pred_i)
                                                tweet_i = [words_keys[words_values.index(x)] for x in tweet_i]
                                                tweet_i = ' '.join(str(x) for x in tweet_i)

                                                tweet_y_i = testY[i]
                                                y_i = [ tagger_keys[tagger_values.index(x)] for x in tweet_y_i]
                                                y_i = ' '.join(str(x) for x in y_i)

                                                f.write("%s |||\t%s\t|||%s\n" %(tweet_i, pred_i, y_i))
                                        f.close()
					"""

					"""
					saveParams(dev_pred, 'predy_dev.pickle')

                                        f = open('Loss_' + params.outfile, 'w')
                                        for i in range(devloss.shape[0]):
                                                pred_i = dev_pred[i].tolist()
                                                pred_i = pred_i[:devlength[i]]
                                                pred_i = ' '.join(str(x) for x in pred_i)
                                                f.write("%f \t %s\n" %(devloss[i], pred_i))
                                        f.close()

                                        f = open('Loss0_' + params.outfile, 'w')
                                        for i in range(devloss0.shape[0]):
                                                pred_i = dev_pred[i].tolist()
                                                pred_i = pred_i[:devlength[i]]
                                                pred_i = ' '.join(str(x) for x in pred_i)
                                                f.write("%f \t %s\n" %(devloss0[i], pred_i))
                                        f.close()			
					"""
					
				
					self.textfile.write("epoches %d  devacc %f  testacc %f trainig time %f test time %f \n" %( eidx + 1, devacc, testacc, end_time1 - start_time1, end_time2 - start_time2 ) )
					self.textfile.flush()
				
			       
        	except KeyboardInterrupt:
            		self.textfile.write( 'classifer training interrupt \n')
			self.textfile.flush()
        	end_time = time.time()
		self.textfile.write("best dev acc: %f  at time %d \n" % (bestdev, best_t))
		print 'bestdev ', bestdev, 'at time ',best_t
        	self.textfile.close()
		
