#! /usr/bin/env python3

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.



import argparse
from signal import signal, SIGPIPE, SIG_DFL
import json
from copy import deepcopy
import os.path
from sys import stderr, exit
import datetime
import inspect

signal(SIGPIPE, SIG_DFL) # Handle broken pipes

version = {}
with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'version.py')) as f: exec(f.read(), version)

def main():

    def warning(msg):
        print('WARNING: {}'.format(msg), file=stderr)

    def error(msg, exit_code=1):
        print('ERROR: {}'.format(msg), file=stderr)
        exit(exit_code)

    parser = argparse.ArgumentParser(description="Create random SNVs, indels and CNVs for each subclone in a tumour sample.")
    parser.add_argument('-v', '--version', action='version', version='%(prog)s {0}'.format(version['__version__']))
    parser.add_argument('-j', '--json', dest='jsonfile', required=True, type=str, help='Json file with parameters')
    parser.add_argument('-c', '--clone', dest='clone', required=True, type=str, help='Clone to be processed')
    parser.add_argument('-x', '--chromosome', dest='chromosome', type=str, help='Chromosome to be processed')

    args = parser.parse_args()
    clo=args.clone

    prochro=args.chromosome
    if prochro==None:
        prochro=''

    with open(args.jsonfile,'r') as file:
        parameters=json.load(file)

    #set default parameter values and give error/warning messages
    if "prefix" not in parameters:
        parameters['prefix'] = ''
    if "reference" not in parameters:
        error('No input genome fasta file provided.')
    if os.path.exists(parameters['reference'] + '.fai'):
        parameters['fai']=(parameters['reference'] + '.fai')
    else:
        error('No fai index file for genome.')
    if "directory" not in parameters:
        warning('No output directory given, using current directory.')
        parameters['directory']='.'
    if "chromosomes" not in parameters:
        if str(prochro)=='':
            parameters['chromosomes']='all'
        else:
            parameters['chromosomes']=prochro
    else:
        if str(prochro)=='':
            pass
        else:
            parameters['chromosomes']=prochro
    #Functions for reading in data----------------------------------------------------------------------------------

    def readinfai(chromosomes,fai,referencefile): #reads in reference and fai files for required chromosomes into dictionaries
        if chromosomes==['all']:
            keepchromos=['chr1','chr2','chr3','chr4','chr5','chr6','chr7','chr8','chr9','chr10','chr11','chr12','chr13','chr14','chr15','chr16','chr17','chr18','chr19','chr20','chr21','chr22']
        else:
            keepchromos=chromosomes
        with open(fai,'r') as geno:
                gen = dict([(line.strip().split("\t")[0], float(line.strip().split("\t")[1])) for line in geno])
        genkeys=list(gen.keys())
        for chro in genkeys:
            if chro not in (keepchromos):
                del gen[chro]
        reference={}
        reflist=[]
        chromo=''
        with open(referencefile,'r') as ref:
            for l in ref:
                if l.startswith('>'):
                    if chromo!='': reference[chromo]=''.join(reflist)
                    reflist=[]
                    chromo=l.strip().split(" ")[0][1:]
                    reference[l.strip().split(" ")[0]]=''
                else:
                    reflist.append(l.strip())
            reference[chromo]=''.join(reflist)
        reflist=''
        for chro in list(reference.keys()):
            if chro not in (keepchromos): del reference[chro]
        return(gen,reference)

    def readinvars(parameters):    #formats structure parameter into dictionary
        with open(parameters['directory'] + '/' + parameters['prefix'] + 'variants.json','r') as file:
                variants=json.load(file)
        return variants

    #Functions for writing output files--------------------------------------------------------------------------------

    def writeblocksfile(directory,prefix,clo,hapvars,modchros,prochro):
        with open(directory + '/' + prefix + clo + prochro + 'blocks.txt','w+') as file:
            for chro in hapvars:
                for hap in hapvars[chro]:
                    file.write(clo+'_'+chro+'_'+hap+'\n')
                    for b in modchros[chro][hap].allblocks:
                        file.write(str(b)+'\n')

    def writecnvfile(directory,prefix,clo,combcnvs,combcnvsa,combcnvsb,prochro):
        with open(directory + '/' + prefix + clo + prochro + 'cnv.txt','w+') as file:
            file.write('Chromosome\tStart\tEnd\tCopy Number\tA Allele\tB Allele\n')
            for chro in combcnvs:
                for b in combcnvs[chro]:
                    for bb in combcnvsa[chro]:
                        if bb.includes(b):
                            acnv=bb.content
                            break
                    for bb in combcnvsb[chro]:
                        if bb.includes(b):
                            bcnv=bb.content
                            break
                    file.write(chro+'\t'+str(b.start)+'\t'+str(int(b.end))+'\t'+str(b.content)+'\t'+str(acnv)+'\t'+str(bcnv)+'\n')

    def writevcffile(directory,prefix,clo,combvcfs,prochro):
        with open(directory + '/' + prefix + clo + prochro + '.vcf','w+') as file:
            file.write('##fileformat=VCFv4.2\n')
            file.write('##fileDate='+str(datetime.datetime.today().strftime('%Y%m%d'))+'\n')
            file.write('##source=heterogenesis_varincorp-'+clo+'\n')
            file.write('##reference=file:'+parameters['reference']+'\n')
            file.write('##INFO=<ID=NS,Number=1,Type=Integer,Description="Number of Samples With Data">\n')
            file.write('##FORMAT=<ID=AF,Number=A,Type=Float,Description="Alt allele frequency">\n')
            file.write('##FORMAT=<ID=TC,Number=1,Type=Integer,Description="Total copies of alt allele">\n')
            file.write('##FORMAT=<ID=HS,Number=1,Type=Character,Description="Haplotypes">\n')
            file.write('##FORMAT=<ID=HC,Number=.,Type=Integer,Description="Total copies of alt allele per haplotype">\n')
            file.write('##FORMAT=<ID=CN,Number=2,Type=Integer,Description="Copy number at position">\n')
            file.write('#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t'+clo+'\n')
            for chro in combvcfs:
                for v in combvcfs[chro]:
                    #write: chromosome, position, ., ref base, alternate base, ., ., 1, FORMAT,frequency, total copies, haplotypes, copies per haplotype, copynumber at position
                    haplotypes=','.join([h[0] for h in combvcfs[chro][v][5]])
                    counts=','.join([str(h[1]) for h in combvcfs[chro][v][5]])
                    file.write(chro+'\t'+str(combvcfs[chro][v][0])+'\t.\t'+str(combvcfs[chro][v][1])+'\t'+str(combvcfs[chro][v][2])+'\t.\t.\tNS=1\tAF:TC:HS:HC:CN\t'+str(combvcfs[chro][v][3])+':'+str(combvcfs[chro][v][4])+':'+haplotypes+':'+counts+':'+str(combvcfs[chro][v][6])+'\n')

    #Functions for generating output file data-------------------------------------------------------------------------------------

    def countvcfs(branches,n):
        for b in branches:
            if b.content=='var':
                n+=1
            else:
                n=countvcfs(b.content,n)
        return n

    def getstart(block):
        return(block.start)

    #These functions aren't used as they would require blocks to be unique and in order
    # def findblockstart(var,blocksfraction):
    #     if len(blocksfraction)>1:
    #         m=int(len(blocksfraction)/2)
    #         if var.start>=blocksfraction[m].start:
    #             blocksfraction=blocksfraction[m:]
    #             var,blocksfraction=findblockstart(var,blocksfraction)
    #         else:
    #             blocksfraction=blocksfraction[:m]
    #             var,blocksfraction=findblockstart(var,blocksfraction)
    #     return var,blocksfraction
    # def findblockend(var,blocksfraction):
    #     if len(blocksfraction)>1:
    #         m=int(len(blocksfraction)/2)-1
    #         if var.end>blocksfraction[m].end:
    #             blocksfraction=blocksfraction[m+1:]
    #             var,blocksfraction=findblockend(var,blocksfraction)
    #         else:
    #             blocksfraction=blocksfraction[:m+1]
    #             var,blocksfraction=findblockend(var,blocksfraction)
    #     return var,blocksfraction

    class BLOCK(object):
        def __init__(self, start, end, content,flag):
            self.start = start
            self.end = end
            self.content=content
            self.flag=flag
        def includes(self, other):  #self completely includes other
            if (other.start >= self.start) and (other.end <= self.end): return True
            return False
        def splitby(self,other):    #other start or end in middle of self
            if (other.end < self.start) or (other.start > self.end): return False   #speeds up code having this check first
            if (other.start > self.start) and (other.start <= self.end): return True
            elif (other.end >= self.start) and (other.end < self.end): return True
            return False
        def __str__(self): return('BLOCK: {}-{}, {}, {}'.format(self.start, self.end, self.content, self.flag))

    class VCFVAR(object):
        def __init__(self, pos, ref, alt, branches,final,haplo):
            self.pos = pos
            self.ref = ref
            self.alt = alt
            self.branches = branches
            self.final = final
            self.haplo = haplo
        def incnv(self,cnv):
            if (cnv.start <= self.pos) and (cnv.end >= self.pos): return True
            return False
        def __str__(self): return('VCF: {}, {}, {}, {}, {}'.format(self.pos, self.ref, self.alt, self.branches, self.final, self.haplo))

    class CNVBRANCH(object):
        def __init__(self, start, end, content):
            self.start = start
            self.end = end
            self.content = content
        def withincnv(self,cnv):
            if (cnv.start <= self.start) and (cnv.end >= self.end): return True
            return False
        def __str__(self): return('{}, {}, {}'.format(self.start, self.end, self.content))

    class MODCHRO(object):
        def __init__(self,chromosome,allblocks,cnblocks,vcfcounts):
            self.chromosome=chromosome
            self.allblocks=allblocks
            self.cnblocks=cnblocks
            self.vcfcounts=vcfcounts
        def getbasestring(self,ref):

            def invert(forward):
                reverse=[]
                substitutions={}
                substitutions['A']='T'
                substitutions['T']='A'
                substitutions['C']='G'
                substitutions['G']='C'
                substitutions['a']='t'
                substitutions['t']='a'
                substitutions['c']='g'
                substitutions['g']='c'
                substitutions['N']='N'
                substitutions['n']='n'
                substitutions['R']='Y'
                substitutions['Y']='R'
                substitutions['y']='r'
                substitutions['r']='y'
                substitutions['S']='S'
                substitutions['s']='s'
                substitutions['W']='W'
                substitutions['w']='w'
                substitutions['K']='M'
                substitutions['M']='K'
                substitutions['k']='m'
                substitutions['m']='k'
                substitutions['B']='V'
                substitutions['V']='B'
                substitutions['b']='v'
                substitutions['v']='b'
       	       	substitutions['D']='H'
       	       	substitutions['H']='D'
       	       	substitutions['d']='h'
       	       	substitutions['h']='d'
                for i in forward[::-1]:
                    reverse.append(substitutions[i])
                return reverse

            basestring=[[]]
            for b in self.allblocks:
                if b.flag=='s':
                    basestring.append([])
                    if b.content=='ref':
                        basestring[-1].extend(reference[self.chromosome][int(b.start)-1:int(b.end)])    #b.start and b.end sometimes get .0 on end so need to be converted to int
                    else:
                        basestring[-1].extend(b.content)
                elif b.flag=='e':
                    if b.content=='ref':
                        basestring[-1].extend(reference[self.chromosome][int(b.start)-1:int(b.end)])    #b.start and b.end sometimes get .0 on end so need to be converted to int
                    else:
                        basestring[-1].extend(b.content)
                    basestring[-2].extend(invert(basestring[-1]))
                    basestring=basestring[:-1]
                elif b.flag=='se':
                    basestring.append([])
                    if b.content=='ref':
                        basestring[-1].extend(reference[self.chromosome][int(b.start)-1:int(b.end)])    #b.start and b.end sometimes get .0 on end so need to be converted to int
                    else:
                        basestring[-1].extend(b.content)
                    basestring[-2].extend(invert(basestring[-1]))
                    basestring=basestring[:-1]
                else:
                    if b.content=='ref':
                        basestring[-1].extend(reference[self.chromosome][int(b.start)-1:int(b.end)])    #b.start and b.end sometimes get .0 on end so need to be converted to int
                    else:
                        basestring[-1].extend(b.content)
            return basestring[-1]

        def __str__(self): return('MODCHRO from {}: {} allblocks, {} cnblocks'.format(self.chromosome, len(self.allblocks), len(self.cnblocks)))

        def updateblocks(self,var):
            if type(var.content)==str:  #if var contains a string (ie. snv or insertion indel) then just insert into allblocks

                for b in self.allblocks:
                    if (var.start <= b.end):
                    #if (var.start >= b.start) and (var.end <= b.end):   #b.includes(var) #runs quicker having the code here
                        insertblock(self.allblocks,b,var)  #split block in half, remove one base form middle, and insert new block
                        break    #break is important to stop multiple copies of the block having the vairant inserted
            elif type(var.content)==int:   #if var contains an integer (ie. cnv or deletion indel) then update both allblocks and cnblocks
                for blocks in self.allblocks,self.cnblocks:
                    if blocks==self.allblocks or var.end-var.start+1>50:    #prevent indel deletions being written to cnblocks

                        # contin=False
                        # while contin==False:
                        #     contin=True
                        #     for b in blocks:
                        #         if ((var.start > b.start) and (var.start <= b.end)) or ((var.end >= b.start) and (var.end < b.end)):    #b.splitby(var) #runs quicker having the code here
                        #             b,blocks=splitblocks(blocks,b,var)  #split block at cnv start and/or end position
                        #             contin=False   #break the while loop only if run through all bs with no splits
                        #             break   #start from beginning of blocks as blocks have now changed


                        firstbreak=False
                        secondbreak=False
                        for b in blocks:
                            if firstbreak==False:
                                if (var.start <= b.end):
                                    addedblocks,blocks=splitblocks(blocks,b,var)
                                    firstbreak=True
                                    for a in addedblocks:
                                        if (var.end <= a.end):
                                            addedblocks,blocks=splitblocks(blocks,a,var)
                                            secondbreak=True
                                            break
                                    if secondbreak==True:
                                        break
                            elif (var.end <= b.end):
                                addedblocks,blocks=splitblocks(blocks,b,var)
                                break

                        #copy blocks withing the var region
                        i=-1
                        copy=[]
                        for b in blocks:
                            i+=1
                            if (b.start >= var.start) and (b.end <= var.end): #var.includes(b) - runs quicker here
                                copy.append(b)
                            elif copy!=[]: #if there are blocks recorded to copy
                                if var.content!=0:
                                    for o in var.flag[::-1]: #for direction of each copy in reverse order
                                        insert=deepcopy(copy)
                                        if o==1:
                                            insert[0].flag='s' #start flag
                                            insert[-1].flag='e' #end flag
                                            if len(insert)==1:
                                                insert[0].flag='se'
                                        blocks[i:i]=insert    #add in copied insert blocks
                                break
                            else:
                                pass
                        #remove original blocks
                        for bl in copy:
                            blocks.remove(bl)
            else:
                print("ERROR")
            return self
        def updatevcf(self,var):
            #if var is a vcfvar (ie. snp or indel) then add to modchro vcfcounts list
            if type(var)==VCFVAR:
                self.vcfcounts.append(deepcopy(var))
            #if var is a cnv then adjust numbers of copies of snvs/indels that are located within it
            elif type(var)==BLOCK:
                for v in self.vcfcounts:    #for each VCFVAR object in MODCHRO.vcfcounts
                    if v.incnv(var):    #if VCFVAR in cnv block
                        v.branches=adjustbranches(v.branches,var)
        def addupfinalvcfs(self):
            for vcfvar in self.vcfcounts:
                vcfvar.final=countvcfs(vcfvar.branches,0)

    def adjustbranches(level,var):  #adjusts record of cnvs overlapping a var in order to calculate how many copies a hap contains. cnvs are recorded in a tree structure with each level coresponding to a cnv position (with the exception of the bottom level which refers to the var position) and each branch on a level refers to a copy.
        if level==[]:   #if copy has been deleted
            return level    #do nothing
        elif level[0].withincnv(var):
            level=[CNVBRANCH(var.start,var.end,deepcopy(level)) for i in range(0,var.content)] #insert new level. need to create new instances of object instead of just copying pointer to the existing instance
            return level
        else:
            level[0].content=adjustbranches(deepcopy(level[0].content),var)  #go to next level down
        return level

    def splitblocks(blocks,spblock,newblock):
        #split block by an overlapping block and return the fragments of the split block
        addedblocks=[]
        if newblock.start > spblock.start and newblock.end < spblock.end:
            leftblock=BLOCK(spblock.start,newblock.start-1,spblock.content,'')
            midblock=BLOCK(newblock.start,newblock.end,spblock.content,'')
            rightblock=BLOCK(newblock.end+1,spblock.end,spblock.content,'')
            if spblock.flag=='s' or spblock.flag=='se':leftblock.flag='s'
            if spblock.flag=='e' or spblock.flag=='se':rightblock.flag='e'
            blocks[blocks.index(spblock):blocks.index(spblock)+1]=[leftblock,midblock,rightblock]
            addedblocks=[leftblock,midblock,rightblock]
        elif newblock.start > spblock.start:
            leftblock=BLOCK(spblock.start,newblock.start-1,spblock.content,'')
            rightblock=BLOCK(newblock.start,spblock.end,spblock.content,'')
            if spblock.flag=='s':leftblock.flag='s'
            blocks[blocks.index(spblock):blocks.index(spblock)+1]=[leftblock,rightblock]
            addedblocks=[leftblock,rightblock]
        elif newblock.end < spblock.end:
            leftblock=BLOCK(spblock.start,newblock.end,spblock.content,'')
            rightblock=BLOCK(newblock.end+1,spblock.end,spblock.content,'')
            if spblock.flag=='e':rightblock.flag='e'
            blocks[blocks.index(spblock):blocks.index(spblock)+1]=[leftblock,rightblock]
            addedblocks=[leftblock,rightblock]
        return addedblocks,blocks


    def insertblock(blocks,spblock,newblock):
        #insert a single base block (from snv or insertion indel) into an existing block and return all 3 resulting blocks (or 2 if the blocks start or end at the same position)
        leftblock=BLOCK(spblock.start,newblock.start-1,spblock.content,'')
        rightblock=BLOCK(newblock.end+1,spblock.end,spblock.content,'')
        if spblock.start==newblock.start: #if newblock starts on same base as existing, don't include leftblock
            if spblock.flag=='s':newblock.flag='s'
            if spblock.flag=='se':
                newblock.flag='s'
                rightblock.flag='e'
            idx=blocks.index(spblock)
            blocks[idx:idx+1]=deepcopy([newblock,rightblock])
        elif spblock.end==newblock.end:  #if newblock ends on same base as existing, don't include rightblock
            if spblock.flag=='e':newblock.flag='e'
            if spblock.flag=='se':
                leftblock.flag='s'
                newblock.flag='e'
            idx=blocks.index(spblock)
            blocks[idx:idx+1]=deepcopy([leftblock,newblock])
        else:
            if spblock.flag=='s':leftblock.flag='s'
            if spblock.flag=='e':rightblock.flag='e'
            if spblock.flag=='se':
                leftblock.flag='s'
                rightblock.flag='e'
            idx=blocks.index(spblock)
            blocks[idx:idx+1]=deepcopy([leftblock,newblock,rightblock])
        return blocks

    def combinecnvs(modchro,gen):
        #put all cnv blocks into one list
        #start with empty block to fill in regions that have been deleted in all copies of a chromosome
        allcnvs=[BLOCK(1,gen[chro],0,'')]
        acnvs=[BLOCK(1,gen[chro],0,'')]
        bcnvs=[BLOCK(1,gen[chro],0,'')]
        for hap in modchro:
            allcnvs.extend(modchro[hap].cnblocks)
            if hap.startswith('A'):
                acnvs.extend(modchro[hap].cnblocks)
            else:
                bcnvs.extend(modchro[hap].cnblocks)
        #split cnv blocks so none overlap
        phase=[allcnvs,acnvs,bcnvs]
        combined=[]
        combineda=[]
        combinedb=[]
        outs=[combined,combineda,combinedb]
        for p in range(3):
            contin=False
            while contin==False:
                contin2=False
                for cnv in allcnvs:
                    contin=False
                    if contin2==True:
                        break
                    for c in phase[p]:
                        if c.splitby(cnv):
                            addedblocks,allcnvs=splitblocks(phase[p],c,cnv)  #split c at cnv start and/or end position
                            contin2=True   #causes break from first loop
                            break   #start from beginning of cnvs as cnvs have now changed
                        else:
                            contin=True    #break the while loop only if run through all cnvs with no splits
            #for each cnv block in allcnvs, if its position is not in recorded then add to combined and sum all cnv blocks with same position in allcnvs
            recorded={}
            for c in phase[p]:
                if c.start not in recorded:
                    outs[p].append(BLOCK(c.start,c.end,sum(s.content for s in phase[p] if s.start==c.start),''))
                recorded[c.start]=''
            #sort cnvs
            outs[p]=sorted(outs[p],key=getstart)
        return combined,combineda,combinedb

    def combinevcfs(modchro,combcnvs):
        #put all vars in dictionaries referenced by position
        allvcfs={}
        for hap in modchro:
            allvcfs[hap]={}
            for v in modchro[hap].vcfcounts:
                allvcfs[hap][v.pos]=v
        #add vars to another dictionary while combining vars with the same position
        combined={}
        for hap in allvcfs:
            for v in allvcfs[hap]:
                if v not in combined:
                    combined[v]=[allvcfs[hap][v].pos,allvcfs[hap][v].ref,allvcfs[hap][v].alt,'round(total/cn,5)','total',[[allvcfs[hap][v].haplo,allvcfs[hap][v].final]],'copynumber']
                else:
                    combined[v][5].append([allvcfs[hap][v].haplo,allvcfs[hap][v].final])
        #Fill in the missing data
        needtodel=[]
        for v in combined:
            #get total number of variant copies
            total=sum([i[1] for i in combined[v][5]])
            if total==0:
                needtodel.append(v)
            else:
                combined[v][4]=total
                #get copy number
                for cnv in combcnvs:
                    if VCFVAR(combined[v][0],'','','','','').incnv(cnv):
                        cn=cnv.content
                combined[v][6]=cn
                #get frequencies
                combined[v][3]=round(total/cn,5)
        for v in needtodel:
            del combined[v]
        return combined

    def writebasestringtofile(parameters,clo,chro,hap,basestring):
        with open(parameters['directory'] + '/' + parameters['prefix'] + clo+chro+hap+'.fasta','w') as file:
            count=0
            file.write('>'+clo+'_'+chro+'_'+hap+'\n')
            for x in basestring:
                if count==80:   #write 80 bases per line
                    file.write('\n')
                    count=0
                file.write(x)
                count+=1
            file.write('\n')

    def createhapvars(clones,gen,variants):
    #create lists of variants by haplotype
        hapvars={}
        for chro in gen:
            hapvars[chro]={}
            for hap in variants[clo][1][chro]:
                hapvars[chro][hap]=[]
                for var in variants[clo][0]:
                    if var[1]==chro:
                        if var[2] in hap:   #if variant haplotype is parent chromosome of or equals the current haplotype, then add var to list
                            hapvars[chro][hap].append(var)
        return hapvars

    def createmodchros(clones,gen,variants):
    #create starting modchros
        modchros={}
        for chro in gen:
            modchros[chro]={}
            for hap in variants[clo][1][chro]:
                modchros[chro][hap]=MODCHRO(chro,[BLOCK(1,gen[chro],'ref','')],[BLOCK(1,gen[chro],1,'',)],[]) #starting allblocks is a block of 1-end containing the refernce, and starting cnblocks is a block of 1-end with copy number of 1.
        return modchros


    #Read in variant_dict file and reference genomes------------------------------------------------------------------------------------------------------------

    variants=readinvars(parameters)

    if clo not in variants:
        print(clo + ' not listed in heterogenesis_vargen.py output. Exiting.')
        exit()

    if type(parameters['chromosomes'])==list:
        chromosomes=parameters['chromosomes']
    else:
        chromosomes=[parameters['chromosomes']]

    gen,reference=readinfai(chromosomes,parameters['fai'],parameters['reference'])  #get dictionaries of genome lengths and sequences


    #Generate vcf and cnv output data and write to files-------------------------------------------------------------------------------------------------
    #convert variants to objects and use to update modchros, and then calculate combined vcfs and cnvs
    modchros=createmodchros(clo,gen,variants)
    hapvars=createhapvars(clo,gen,variants)
    combcnvs={}    #dictionary of combined copy numbers for each chromosome
    combcnvsa={}
    combcnvsb={}
    combvcfs={}    #dictionary of combined vcfs for each chromosome
    for chro in hapvars:
        for hap in hapvars[chro]:
            for var in hapvars[chro][hap]:
                if var[0]=='cnv':
                    modchros[chro][hap].updateblocks(BLOCK(var[3],var[3]+var[4]-1,var[5],var[6]))
                    modchros[chro][hap].updatevcf(BLOCK(var[3],var[3]+var[4]-1,var[5],''))
                elif var[0]=='indel':
                    if var[7]=='i':
                        modchros[chro][hap].updateblocks(BLOCK(var[3],var[3],var[6],''))
                    else:
                        modchros[chro][hap].updateblocks(BLOCK(var[3]+1,var[3]+1+var[4]-1,0,''))
                    modchros[chro][hap].updatevcf(VCFVAR(var[3],var[5],var[6],[CNVBRANCH(var[3],var[3],'var')],'',hap)) #VCFVAR object starts with a single CNVBRANCH which contains the variant instead of a CNV
                elif var[0]=='snv':
                    modchros[chro][hap].updateblocks(BLOCK(var[3],var[3],var[5],''))
                    modchros[chro][hap].updatevcf(VCFVAR(var[3],var[4],var[5],[CNVBRANCH(var[3],var[3],'var')],'',hap)) #VCFVAR object starts with a single CNVBRANCH which contains the variant instead of a CNV
                elif var[0]=='aneu':
                    pass    #no need to do anything
            modchros[chro][hap].addupfinalvcfs()
            print(str(datetime.datetime.now())+' : Processed mutations for '+chro+hap)
        combcnvs[chro],combcnvsa[chro],combcnvsb[chro]=combinecnvs(modchros[chro],gen)
        print(str(datetime.datetime.now())+' : Calculated copy numbers for '+chro)
        combvcfs[chro]=combinevcfs(modchros[chro],combcnvs[chro])
        print(str(datetime.datetime.now())+' : Calculated variant allele frequencies for '+chro)

    #write output files ------------------------------------------------------------------------------------------------------
    #write variant files
    #writeblocksfile(parameters['directory'],parameters['prefix'],clo,hapvars,modchros)   #This can be uncommented and used for testing if needed
    writecnvfile(parameters['directory'],parameters['prefix'],clo,combcnvs,combcnvsa,combcnvsb,prochro)
    print(str(datetime.datetime.now())+' : Written copy numbers file')
    writevcffile(parameters['directory'],parameters['prefix'],clo,combvcfs,prochro)
    print(str(datetime.datetime.now())+' : Written vcf file')
    #Generate genome sequences and write to files
    for chro in hapvars:
        for hap in hapvars[chro]:
            writestring=modchros[chro][hap].getbasestring(gen[chro])
            writebasestringtofile(parameters,clo,chro,hap,writestring)
            print(str(datetime.datetime.now())+' : Written fasta sequence for '+chro+hap)
# If run as main, run main():
if __name__ == '__main__': main()
