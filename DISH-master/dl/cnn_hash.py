from caffe import layers as L, params as P, to_proto
from caffe.proto import caffe_pb2

import sys
sys.path.extend(['./'])
import numpy as np
from multilabel_softmax_data_layer import *

import os

class CNN_hash(object):
	def __init__(self, n_bit):
		# some configures
		self.init_proto = "dl/"+str(n_bit)+"_python_cifar10_6conv_hashloss.prototxt"
		self.train_proto = "dl/"+str(n_bit)+"_python_cifar10_6conv_softmax.prototxt"
		self.solver_proto = "dl/"+str(n_bit)+"_hash_model_solver.prototxt"
		self.device = 6
		self.fine_model_dir = ""#dl/dl_snapshots/cifar10_6conv_iter_60000.caffemodel"
		self.out_blob = "bn"
		self.snapshot_file_prefix = 'dl/dl_snapshots/cifar10_6conv'
		self.hash_model_dir = 'dl/hash_model_'+str(n_bit)+'.caffemodel'

		self.n_bit = n_bit
		self.n_iter = 0

		caffe.set_mode_gpu()
		caffe.set_device(self.device)
		
		self.make_solver()
		os.environ['GLOG_minloglevel'] = '2'
		self.solver = caffe.SGDSolver(self.solver_proto)
		os.environ['GLOG_minloglevel'] = '1'
		assert self.solver.net.blobs[self.out_blob].data.shape[1] == self.n_bit

		if self.fine_model_dir != "":
			self.solver.net.copy_from(self.fine_model_dir)
			self.solver.test_nets[0].share_with(self.solver.net)
		# self.solver.snapshot()
		self.solver.net.save(self.hash_model_dir)
	
	def make_solver(self):
		s = caffe.proto.caffe_pb2.SolverParameter()
		# consider init proto
		if self.n_iter == 0 and self.init_proto != "":
			s.net = self.init_proto
		else:
			s.net = self.train_proto
		
		# basic learning configures, can be modified
		s.test_iter.extend([10])
		s.test_interval = 1000
		s.base_lr = 0.01 / (2*self.n_iter+1)
		s.momentum = 0.9
		s.weight_decay = 0.001
		s.lr_policy = "multistep"
		s.gamma = 0.1
		s.snapshot = 5000
		s.display = 200
		s.snapshot_prefix = self.snapshot_file_prefix
		s.solver_mode = caffe.proto.caffe_pb2.SolverParameter.GPU

		# step value: different form of learning policy
		if self.n_iter == 0:
			s.stepvalue.extend([40000, 50000])
			s.max_iter = 60000
		elif self.n_iter == 1:
			s.stepvalue.extend([30000, 35000])
			s.max_iter = 40000
		else:
			s.stepvalue.extend([10000, 12000])
			s.max_iter = 15000

		with open(self.solver_proto, 'w') as f:
			f.write(str(s))
	
	def train(self, traindata, H, trainlabel=None):
		self.make_solver()
		os.environ['GLOG_minloglevel'] = '2'
		self.solver = caffe.SGDSolver(self.solver_proto)
		os.environ['GLOG_minloglevel'] = '1'
		assert self.solver.net.blobs[self.out_blob].data.shape[1] == self.n_bit
		self.solver.net.copy_from(self.hash_model_dir)
		self.solver.test_nets[0].share_with(self.solver.net)

		self.solver.net.layers[0].batch_loader.update_data(traindata, H, trainlabel)
		self.solver.test_nets[0].layers[0].batch_loader.update_data(traindata, H, trainlabel)

		self.solver.solve()
		self.solver.net.save(self.hash_model_dir)
		self.n_iter += 1

	def predict(self, traindata, layer='bn'):
		self.solver.test_nets[0].layers[0].batch_loader.update_data(traindata)
		shape = list(self.solver.test_nets[0].blobs[layer].data.shape)
		shape[0] = len(traindata)
		Y = np.zeros(shape)

		_cur = 0
		_batch_size = self.solver.test_nets[0].layers[0].batch_size
		_n = len(traindata)
		while _cur < _n:
			self.solver.test_nets[0].forward()
			if _cur+_batch_size < _n:
				Y[_cur:_cur+_batch_size] = self.solver.test_nets[0].blobs[layer].data
			else:
				Y[_cur:] = self.solver.test_nets[0].blobs[layer].data[:_n-_cur]
			_cur += _batch_size

		return Y
	
