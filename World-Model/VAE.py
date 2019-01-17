
# coding: utf-8

# In[22]:
import numpy as np
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torch


# In[23]:


class Encoder(nn.Module):
    def __init__(self,img_channels, latent_size):
        super(Encoder,self).__init__()
        self.img_channels = img_channels
        self.latent_size = latent_size
        self.conv1 = nn.Conv2d(in_channels = img_channels, out_channels = 32, kernel_size = 4, stride = 2)
        self.conv2 = nn.Conv2d(in_channels = 32, out_channels = 64, kernel_size = 4, stride = 2)
        self.conv3 = nn.Conv2d(in_channels = 64, out_channels = 128, kernel_size = 4, stride = 2)
        self.conv4 = nn.Conv2d(in_channels = 128, out_channels = 256, kernel_size = 4, stride = 2)
        
        self.mu = nn.Linear(in_features = 2*2*256, out_features = latent_size)
        self.logsigma = nn.Linear(in_features = 2*2*256, out_features = latent_size)
    
    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = F.relu(self.conv3(x))
        x = F.relu(self.conv4(x))
        x = x.view(x.size(0), -1)
        
        mu = self.mu(x)
        logsigma = self.logsigma(x)
        
        return mu, logsigma


# In[24]:


class Decoder(nn.Module):
    def __init__(self,img_channels, latent_size):
        super(Decoder,self).__init__()
        self.img_channels = img_channels
        self.latent_size = latent_size
        
        self.linear1 = nn.Linear(latent_size,1024)
        self.deconv1 = nn.ConvTranspose2d(in_channels = 1024, out_channels = 128, kernel_size = 5, stride = 2)
        self.deconv2 = nn.ConvTranspose2d(in_channels = 128, out_channels = 64, kernel_size = 5, stride = 2)
        self.deconv3 = nn.ConvTranspose2d(in_channels = 64, out_channels = 32, kernel_size = 6, stride = 2)
        self.deconv4 = nn.ConvTranspose2d(in_channels = 32, out_channels = img_channels, kernel_size = 6, stride = 2)
        
    def forward(self,z):
        z = F.relu(self.linear1(z))
        z = z.unsqueeze(-1).unsqueeze(-1)
        z = F.relu(self.deconv1(z))
        z = F.relu(self.deconv2(z))
        z = F.relu(self.deconv3(z))
        z = torch.sigmoid(self.deconv4(z))
        return z


# In[25]:


class VAE(nn.Module):
    def __init__(self,img_channels, latent_size):
        super(VAE,self).__init__()
        self.latent_size = latent_size
        self.encoder = Encoder(img_channels, latent_size)
        self.decoder = Decoder(img_channels, latent_size)
        
    def forward(self,x):
        mu,logsigma = self.encoder(x)
        
        sigma = logsigma.exp()
        epsilon = torch.randn_like(sigma)
        z = epsilon.mul(sigma).add_(mu)   
        
        recon_x = self.decoder(z)
        return recon_x, mu, logsigma


# $KL_{loss}=-\frac{1}{2}(2\log(\sigma_1)-\sigma_1^2-\mu_1^2+1)$  if σ is the standard deviation.   
# Warning, if σ if the variance, $=-\frac{1}{2}(\log(\sigma_1)-\sigma_1-\mu^2_1+1)$

# In[26]:


class ConvVAE():
    def __init__(self,img_channels, latent_size, learning_rate):
        self.cuda = torch.cuda.is_available()
        self.device = torch.device("cuda" if self.cuda else "cpu")
        print("ConVAE running on GPU" if self.cuda else "ConVAE running on CPU")
        self.vae = VAE(img_channels, latent_size).to(self.device)
        self.learning_rate = learning_rate
        self.optimizer = optim.Adam(self.vae.parameters(), lr = learning_rate)
        self.losses = []
        self.BCEs = []
        self.KLDs = []
        self.epoch_trained = 0
        
    def train(self, batch_img, batch_size, nb_epochs):
        if self.epoch_trained>0: print(f'ConvVAE already trained on {self.epoch_trained} epochs')
        self.epoch_trained += nb_epochs
        batch_img = batch_img.to(self.device)
        for epoch in range(1,nb_epochs+1):
            loss_epoch = 0
            for batch in torch.split(batch_img, 40, dim=0):
                self.vae.train()
                self.optimizer.zero_grad()
                recon_x, mu, logsigma = self.vae(batch)
                
                BCE = F.mse_loss(recon_x, batch, reduction='sum')
                #If the training is bad, add a threshold to KLD
                KLD = -0.5 * torch.sum(1 + 2 * logsigma - mu.pow(2) - (2 * logsigma).exp())
                loss = BCE + KLD
                loss_epoch+=loss
                self.losses.append(loss)
                self.BCEs.append(BCE)
                self.KLDs.append(KLD)
                    
                loss.backward()
                self.optimizer.step()
            
            if epoch%max(int(nb_epochs/10),1)==0:
                print(f'Epoch {epoch}: loss = {round(float(loss_epoch),4)}') #CHECK THIS LINE, voir s on peut utiliser tdqm
        
        return recon_x
        
    def __call__(self,batch_img):
        return self.vae(batch_img.to(self.device))[0]

    def display_reconstruction(self,batch_img, id_img):
        recon_batch_img = self.vae(batch_img[id_img,:,:,:].unsqueeze(0).to(self.device))[0].detach()
        import matplotlib.pyplot as plt
        
        plt.figure(figsize = (10,20))
        for channel in range(3):
            img = np.transpose(batch_img[id_img,:,:,:].numpy(),(1,2,0))
            plt.subplot(4,2,2*channel+1)
            plt.imshow(img[:,:,channel]*255)
            plt.axis('off')
            img = np.transpose(np.array(recon_batch_img[0,:,:,:].detach()*255),(1,2,0))
            plt.subplot(4,2,2*(channel+1))
            plt.imshow(np.clip(img,0,255)[:,:,channel])
            plt.axis('off')
            
        plt.subplot(4,2,7)
        plt.imshow(np.transpose(batch_img[id_img,:,:,:].numpy(),(1,2,0)))
        plt.axis('off')
        img = np.transpose(np.array(recon_batch_img[0,:,:,:].detach()),(1,2,0))
        plt.subplot(4,2,8)
        plt.imshow(np.clip(img,0,1))
        plt.axis('off')
        plt.subplots_adjust(wspace=0, hspace=0)
        plt.show()
        
    def save(self,path=None):
        if path==None:
            torch.save(self.vae,'./models/ConvVAE_weights.pt')
            torch.save(self.optimizer,'./models/ConvVAE_optimizer.pt')
        else:
            torch.save(self.vae,path+'_weights.pt')
            torch.save(self.optimizer,path+'_optimizer.pt')
        print('Model and Optimizer saved')
        
    def load(self,path=None):
        path = './models/ConvVAE' if path==None else path
        self.vae = torch.load(path+'_weights.pt')
        self.optimizer = torch.load(path+'_optimizer.pt')
        self.vae.eval()
        print('Model and Optimizer loaded')