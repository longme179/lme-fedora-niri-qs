"""Gowall CLI adapter: isolated outputs, explicit preview/export/apply."""
# SPDX-License-Identifier: GPL-3.0-or-later
from pathlib import Path
import os
import re
import shlex
import shutil
import tempfile
import uuid
from wallpaper import image_path

OPERATIONS=('palette','upscale','extract','brightness','contrast','saturation','grayscale','invert','pixelate','resize')


def command(operation,source,destination,options):
    if operation not in OPERATIONS: raise ValueError('Choose a supported gowall operation')
    def number(key,default,low,high):
        value=options.get(key,default)
        if type(value) not in (int,float) or not low<=value<=high: raise ValueError('Invalid '+key)
        return str(value)
    if operation=='palette':
        theme=options.get('theme','dracula')
        if not isinstance(theme,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_. -]{0,79}',theme): raise ValueError('Choose a gowall theme')
        args=['convert',source,'--theme',theme]
    elif operation=='upscale':
        scale=options.get('scale',2)
        if type(scale) is not int or scale not in (2,3,4): raise ValueError('Upscale supports 2×, 3× or 4×')
        args=['upscale',source,'--scale',str(scale)]
    elif operation=='extract':
        count=options.get('colors',8)
        if type(count) is not int or not 2<=count<=16: raise ValueError('Extract 2–16 colors')
        return ['extract',source,'--colors',str(count)]
    elif operation in ('brightness','contrast','saturation'):
        low,high,default=(.1,10,1) if operation=='brightness' else (-99,99,0)
        args=['effects',{'brightness':'br'}.get(operation,operation),source,
              '--percentage' if operation=='saturation' else '--factor',number('amount',default,low,high)]
    elif operation=='grayscale': args=['effects','grayscale',source]
    elif operation=='pixelate': args=['pixelate',source,'--scale',number('amount',15,1,25)]
    elif operation=='resize':
        size=options.get('dimensions','1920x1080')
        if not isinstance(size,str) or not re.fullmatch(r'[1-9][0-9]{0,4}x[1-9][0-9]{0,4}',size): raise ValueError('Enter dimensions such as 1920x1080')
        args=['resize',source,'--dimensions',size]
    else: args=['invert',source]
    return args+['--output',str(destination),'--preview','false']


class ImageUtilities:
    def __init__(self,runner,wallpapers,launchpad):
        self.runner,self.wallpapers,self.launchpad=runner,wallpapers,launchpad
        self.state={'themes':[],'images':[],'colors':[],'operation':'','log':''}
        self.directory=None

    def themes(self):
        output=self.runner.run('gowall','list',timeout=10,input='')
        output=re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]','',output)
        return sorted(set(line.strip() for line in output.splitlines() if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_. -]{0,79}',line.strip())))[:512]

    def sources(self,value):
        if not isinstance(value,list) or not 1<=len(value)<=24: raise ValueError('Choose 1–24 images')
        paths=list(dict.fromkeys(image_path(path) for path in value))
        if any(not Path(path).is_file() for path in paths): raise ValueError('An input image no longer exists')
        return paths

    def generate(self,request):
        paths=self.sources(request.get('paths'))
        operation=request.get('operation');options=request.get('options',{})
        if not isinstance(options,dict): raise ValueError('Invalid gowall options')
        # Validate every option before creating output or invoking gowall.
        for path in paths: command(operation,path,'/preview.png',options)
        self.runner.executable('gowall')
        cache=Path(os.environ.get('XDG_CACHE_HOME',Path.home()/'.cache'))/'lme-shell/gowall'
        cache.mkdir(parents=True,exist_ok=True,mode=0o700)
        directory=Path(tempfile.mkdtemp(prefix='job-',dir=cache));images=[];colors=[];logs=[]
        try:
            for index,source in enumerate(paths):
                output=directory/(str(index)+'-'+Path(source).stem[:100]+'.png')
                log=self.runner.run('gowall',*command(operation,source,output,options),timeout=600 if operation=='upscale' else 120,input='')
                logs.append(log[-2000:])
                if operation=='extract': colors.extend(re.findall(r'#[0-9a-fA-F]{6}\b',log))
                elif not output.is_file() or not output.stat().st_size: raise ValueError('gowall produced no image. For first-time upscale, use Setup in terminal, then generate again.')
                else:
                    with output.open('rb') as image:
                        if image.read(8)!=b'\x89PNG\r\n\x1a\n': raise ValueError('Gowall preview must be PNG. Choose a static source image.')
                    images.append(dict(path=str(output),url=output.as_uri(),name=Path(source).name))
            result=dict(themes=self.state['themes'],images=images,colors=list(dict.fromkeys(colors))[:64],operation=operation,log='\n'.join(logs)[-4000:])
            previous=self.directory;self.directory=directory
            if previous: shutil.rmtree(previous,ignore_errors=True)
            return result
        except BaseException:
            shutil.rmtree(directory,ignore_errors=True);raise

    def image(self,path):
        if not isinstance(path,str) or not any(item['path']==path for item in self.state['images']) or not Path(path).is_file(): raise ValueError('Generate an image preview first')
        return Path(path)

    def save(self,path,destination):
        source=self.image(path);target=Path(image_path(destination))
        if target.suffix.lower()!='.png': raise ValueError('Save the processed image with a .png extension')
        # Create exclusively: never overwrite an original or a previous export.
        created=False
        try:
            with source.open('rb') as content,target.open('xb') as output:
                created=True
                shutil.copyfileobj(content,output);output.flush();os.fsync(output.fileno())
        except OSError:
            if created: target.unlink(missing_ok=True)
            raise
        return 'Image saved to '+str(target)

    def apply(self,path,output):
        source=self.image(path)
        directory=Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))/'lme-shell/wallpapers'
        directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        target=directory/(uuid.uuid4().hex+'.png')
        try:
            with target.open('xb') as stream,source.open('rb') as content: shutil.copyfileobj(content,stream)
            return self.wallpapers.apply(str(target),output)
        except BaseException:
            target.unlink(missing_ok=True);raise

    def setup(self,path,terminal):
        source=self.sources([path])[0]
        # Gowall's own terminal prompt asks before it downloads the Vulkan upscaler.
        args=[self.runner.executable('gowall'),'upscale',source,'--preview','false']
        entry=dict(name='Gowall upscale setup',command=shlex.join(args),kind='command',terminal=True,cwd='')
        return self.launchpad.run('gowall-setup',{'gowall-setup':entry},terminal)
