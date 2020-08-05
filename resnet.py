# -*- coding: utf-8 -*-
"""resnet.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1bWs-csmzz4EZgVExHTeoq1lp0-6kqyKl

#Import the libraries
"""

import torch
import numpy as np

from torchvision import datasets
import torchvision.transforms as transforms
from torch.utils.data.sampler import SubsetRandomSampler

import torch.nn as nn
import torch.nn.functional as F
import torch.nn.init as init

import torch.optim as optim

train_on_gpu = torch.cuda.is_available()
device = torch.device("cuda" if train_on_gpu else "cpu")

"""#Download the training data from cifar-10"""

# Number of subprocesses to use for data loading
num_workers = 0

# How many samples per batch to load
batch_size = 20

# Percentage of training set to use as validation。
n_valid = 0.2

# Convert data to a normalized torch.FloatTensor
norm_mean = [0.485, 0.456, 0.406]
norm_std = [0.229, 0.224, 0.225]

train_transform = transforms.Compose([
    transforms.Resize(32),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.RandomCrop(32, padding=4),
    transforms.ToTensor(),
    transforms.Normalize(norm_mean, norm_std),
])

valid_transform = transforms.Compose([
    transforms.Resize((32, 32)),
    transforms.ToTensor(),
    transforms.Normalize(norm_mean, norm_std),
])
# Select training_set and testing_set
train_data = datasets.CIFAR10("data",train= True,download=True,transform = train_transform)

test_data = datasets.CIFAR10("data",train= False,download=True,transform = valid_transform)

# Get indices for training_set and validation_set
n_train = len(train_data)
indices = list(range(n_train))
np.random.shuffle(indices)
split = int(np.floor(n_valid * n_train))
train_idx, valid_idx = indices[split:], indices[:split]

# Define samplers for obtaining training and validation
train_sampler = SubsetRandomSampler(train_idx)
valid_sampler = SubsetRandomSampler(valid_idx)

# Prepare data loaders (combine dataset and sampler)
train_loader = torch.utils.data.DataLoader(train_data, batch_size = batch_size,
                       sampler = train_sampler,
                       num_workers = num_workers)

valid_loader = torch.utils.data.DataLoader(train_data, batch_size = batch_size,
                       sampler = valid_sampler,
                       num_workers = num_workers)

test_loader = torch.utils.data.DataLoader(test_data, 
                       batch_size = batch_size,
                       num_workers = num_workers)

# Specify the image classes
classes = ["airplane", "automobile", "bird", "cat", "deer", "dog", "frog",
          "horse", "ship", "truck"]

"""#Define the Resnet acrh

##step 1 define the basic block
"""

class LambdaLayer(nn.Module):
  def __init__(self, lambd):
      super(LambdaLayer, self).__init__()
      self.lambd = lambd

  def forward(self, x):
      return self.lambd(x)
      
def _weights_init(m):
  classname = m.__class__.__name__
  if isinstance(m, nn.Linear) or isinstance(m, nn.Conv2d):
    init.kaiming_normal_(m.weight)

class BasicBlock(nn.Module):
  expansion = 1

  def __init__(self, in_planes, planes, stride=1):
    super(BasicBlock, self).__init__()
    self.conv1 = nn.Conv2d(in_planes, planes, kernel_size=3, 
                           stride=stride, padding=1, 
                           bias=False)
    self.bn1 = nn.BatchNorm2d(planes)
    self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, 
                           stride=1, padding=1, 
                           bias=False)
    self.bn2 = nn.BatchNorm2d(planes)
    self.relu = nn.ReLU(inplace=True)

    ###define the downsample method for shortcut
    self.shortcut = nn.Sequential()
    if stride != 1 or in_planes != planes:
      ###For CIFAR10 ResNet paper uses option A
      self.shortcut = LambdaLayer(lambda x:
                      F.pad(x[:, :, ::2, ::2], 
                      (0, 0, 0, 0, planes//4, 
                       planes//4), "constant", 0))
  
  def forward(self, x):
    out = self.relu(self.bn1(self.conv1(x)))
    out = self.bn2(self.conv2(out))
    out += self.shortcut(x)
    out = self.relu(out)
    return out

"""##step2 define the resnet 
in paper
"""

class ResNet(nn.Module):
  def __init__(self, block, num_blocks, num_classes=10):
    super(ResNet, self).__init__()
    self.in_planes = 64

    #7,7,64,stride=2 output 112
    self.conv1 = nn.Conv2d(3, self.in_planes, kernel_size=7, stride=2, padding=3, bias=False)
    self.bn1 = nn.BatchNorm2d(self.in_planes)
    self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
    self.relu = nn.ReLU(inplace=True)

    #output 56,28,14,7
    self.layer1 = self._make_layer(block, 64, num_blocks[0], stride=1)
    self.layer2 = self._make_layer(block, 128, num_blocks[1], stride=2)
    self.layer3 = self._make_layer(block, 256, num_blocks[2], stride=2)
    self.layer4 = self._make_layer(block, 512, num_blocks[2], stride=2)

    #fc layer output 1*1
    self.linear = nn.Linear(512*block.expansion, num_classes)

    self.apply(_weights_init)

  def _make_layer(self, block, planes, num_blocks, stride):
    #downsampling in first block
    strides = [stride] + [1]*(num_blocks-1)
    layers = []
    for stride in strides:
        layers.append(block(self.in_planes, planes, stride))
        self.in_planes = planes * block.expansion

    return nn.Sequential(*layers)

  def forward(self, x):
    out = self.conv1(x)
    out = self.bn1(out)
    out = self.relu(out)
    out = self.maxpool(out)

    out = self.layer1(out)
    out = self.layer2(out)
    out = self.layer3(out)
    out = self.layer4(out)

    out = F.avg_pool2d(out, out.size()[3])
    out = out.view(out.size(0), -1)
    out = self.linear(out)
    return out

"""##step 3 define resnt 18
[2,2,2,2] blocks
"""

def resnet18():
  return ResNet(BasicBlock, [2,2,2,2])

"""#Setting up the train paramter"""

BATCH_SIZE = 128
learnrate = 0.1
log_interval = 1
val_interval = 1
start_epoch = -1
milestones = [92, 136]  # divide it by 10 at 32k and 48k iterations
model = resnet18()
MAX_EPOCH = 182 # 64000 / (45000 / 128) = 182 epochs

model.to(device)
print(model)
criterion = nn.CrossEntropyLoss()
optimizer = optim.SGD(model.parameters(), lr=learnrate, momentum=0.9, weight_decay=1e-4)  # 选择优化器
scheduler = optim.lr_scheduler.MultiStepLR(optimizer, gamma=0.1, milestones=milestones)

"""#Start training"""

valid_loss_min = np.Inf

for epoch in range(start_epoch + 1, MAX_EPOCH):

    # 训练(data_loader, model, loss_f, optimizer, epoch_id, device, max_epoch)
   
    # keep track of training and validation loss
    train_loss = 0.0
    valid_loss = 0.0
    
    ###################
    # train the model #
    ###################
    model.train()
    for data, target in train_loader:
      # move tensors to GPU if CUDA is available
      if train_on_gpu:
          data, target = data.cuda(), target.cuda()
      # clear the gradients of all optimized variables
      optimizer.zero_grad()
      # forward pass: compute predicted outputs by passing inputs to the model
      output = model(data)
      # calculate the batch loss
      loss = criterion(output, target)
      # backward pass: compute gradient of the loss with respect to model parameters
      loss.backward()
      # perform a single optimization step (parameter update)
      optimizer.step()
      # update training loss
      train_loss += loss.item()*data.size(0)
        
    ######################    
    # validate the model #
    ######################
    model.eval()
    for data, target in valid_loader:
      # move tensors to GPU if CUDA is available
      if train_on_gpu:
          data, target = data.cuda(), target.cuda()
      # forward pass: compute predicted outputs by passing inputs to the model
      output = model(data)
      # calculate the batch loss
      loss = criterion(output, target)
      # update average validation loss 
      valid_loss += loss.item()*data.size(0)
  
    # calculate average losses
    train_loss = train_loss/len(train_loader.dataset)
    valid_loss = valid_loss/len(valid_loader.dataset)
    scheduler.step()  # 更新学习率
        
    # print training/validation statistics 
    print('Epoch: {} \tTraining Loss: {:.6f} \tValidation Loss: {:.6f}'.format(
        epoch, train_loss, valid_loss))
    
    # save model if validation loss has decreased
    if epoch > (MAX_EPOCH/2) and valid_loss <= valid_loss_min:
        print('Validation loss decreased ({:.6f} --> {:.6f}).  Saving model ...'.format(
        valid_loss_min,
        valid_loss))
        torch.save(model.state_dict(), 'model_cifar.pt')
        valid_loss_min = valid_loss

# track test loss
test_loss = 0.0
class_correct = list(0. for i in range(10))
class_total = list(0. for i in range(10))

model.eval()
# iterate over test data
for data, target in test_loader:
    # move tensors to GPU if CUDA is available
    if train_on_gpu:
        data, target = data.cuda(), target.cuda()
    # forward pass: compute predicted outputs by passing inputs to the model
    output = model(data)
    # calculate the batch loss
    loss = criterion(output, target)
    # update test loss 
    test_loss += loss.item()*data.size(0)
    # convert output probabilities to predicted class
    _, pred = torch.max(output, 1)    
    # compare predictions to true label
    correct_tensor = pred.eq(target.data.view_as(pred))
    correct = np.squeeze(correct_tensor.numpy()) if not train_on_gpu else np.squeeze(correct_tensor.cpu().numpy())
    # calculate test accuracy for each object class
    for i in range(batch_size):
        label = target.data[i]
        class_correct[label] += correct[i].item()
        class_total[label] += 1

# average test loss
test_loss = test_loss/len(test_loader.dataset)
print('Test Loss: {:.6f}\n'.format(test_loss))

for i in range(10):
    if class_total[i] > 0:
        print('Test Accuracy of %5s: %2d%% (%2d/%2d)' % (
            classes[i], 100 * class_correct[i] / class_total[i],
            np.sum(class_correct[i]), np.sum(class_total[i])))
    else:
        print('Test Accuracy of %5s: N/A (no training examples)' % (classes[i]))

print('\nTest Accuracy (Overall): %2d%% (%2d/%2d)' % (
    100. * np.sum(class_correct) / np.sum(class_total),
    np.sum(class_correct), np.sum(class_total)))