
import os
import commands

try:
	import lsjon as json
except:
	import json

try:
	from PIL import Image as pil_image
except:
	try:
		import Image as pil_image
	except:
		pil_image = None

class ConfigurationError(Exception):
	pass

class MetadataError(Exception):
	pass

class ManifestFactory(object):
	metadata_base = ""
	image_base = ""
	add_lang = False

	def __init__(self, mdbase="", imgbase="", lang="en"):
		if mdbase:
			self.set_base_metadata_uri(mdbase)
		if imgbase:
			self.set_base_image_uri(imgbase)
		self.default_lang = lang
		self.add_lang = False
		self.context_uri = "http://www.shared-canvas.org/ns/context.json"
		self.iiif_profile_uri = "http://library.stanford.edu/iiif/image-api/"
		self.iiif_version = -1
		self.iiif_level = -1
		self.debug_level = "warn"

		# Try to find ImageMagick's identify
		try:
			self.whichid = commands.getoutput('which identify')
		except:
			# No IM or not unix
			self.whichid = ""

	def set_debug(self, typ):
		if typ in ['error', 'warn']:
			self.debug_level = typ
		else:
			raise ConfigurationError("Only levels are 'error' and 'warn'")

	def assert_base_metadata_uri(self):
		if not self.metadata_base:
			raise ConfigurationError("Metadata API Base URI is not set")

	def assert_base_image_uri(self):
		if not self.image_base:
			raise ConfigurationError("IIIF Image API Base URI is not set")

	def set_base_metadata_uri(self, uri):
		if not uri:
			raise ValueError("Must provide a URI to set the base URI to")
		elif uri[-1] != "/":
			uri += "/"
		self.metadata_base = uri

	def set_base_image_uri(self, uri):
		if not uri:
			raise ValueError("Must provide a URI to set the base URI to")
		elif uri[-1] != "/":
			uri += "/"	
		self.image_base = uri

	def set_default_label_language(self, lang):
		self.default_lang = lang

	def set_iiif_image_conformance(self, version, lvl):
		if not version in ['1.0', '1.1', 1.0, 1.1]:
			raise ConfigurationError("Only versions 1.1 and 1.0 are known")
		if not lvl in [0,1,2]:
			raise ConfigurationError("Level must be 0, 1 or 2")			
		self.iiif_version = float(version)
		self.iiif_level = lvl
		if self.iiif_version == 1.1:
			self.iiif_profile_uri += ("1.1/compliance.html#level%s" % lvl)
		else:
			self.iiif_profile_uri += ("compliance.html#level%s" % lvl)			
	
	def manifest(self, ident="", label="", mdhash={}):
		if not ident:
			ident = "manifest"
		self.assert_base_metadata_uri()
		return Manifest(self, ident, label, mdhash)

	def manifest(self, ident="manifest", label="", mdhash={}):
		self.assert_base_metadata_uri()
		return Manifest(self, ident, label, mdhash)

	def sequence(self,ident="", label="", mdhash={}):
		if ident:
			self.assert_base_metadata_uri()
		return Sequence(self, ident, label, mdhash)

	def canvas(self,ident="", label="", mdhash={}):
		if ident:
			self.assert_base_metadata_uri()
		return Canvas(self, ident, label, mdhash)

	def annotation(self, ident="", label=""):
		if ident:
			self.assert_base_metadata_uri()
		return Annotation(self, ident, label=label)

	def annotationList(self, ident="", label="", mdhash={}):
		if not ident:
			raise MetadataError("AnnotationLists must have a real identity")
		return AnnotationList(self, ident, label, mdhash)

	def image(self, ident, label="", iiif=False):
		if not ident:
			raise MetadataError("Images must have a real identity")			
		return Image(self, ident, label, iiif)

	def choice(self, default, rest):
		return Choice(self, default, rest)

	def text(self, txt, language, format):
		return Text(self, txt, language, format)

class BaseMetadataObject(object):
	def __init__(self, factory, ident="", label="", mdhash={}, **kw):
		self._factory = factory
		if ident:
			self.id = factory.metadata_base + self.__class__._uri_segment + ident + '.json'
		else:
			self.id = ""
		self.type = self.__class__._type
		self.label = ""
		if label:
			self.set_label(label)
		self.metadata = []
		if mdhash:
			self.set_metadata(mdhash)
		self.description = ""
		self.attribution = ""
		self.license = ""
		self.service = ""
		self.seeAlso = ""
		self.within = ""

	def langhash_to_jsonld(self, lh):
		# {"fr": "something in french", "en": "something in english"}
		# --> [{"@value": "something in french", "@language": "fr"}, ...]
		l = []
		for (k,v) in lh.items():
			l.append({"@value":v, "@language":k})
		return l

	def set_metadata(self, mdhash):
		# In:  {label:value}
		# Set: {"label":label, "value":value}
		for (k,v) in mdhash.items():
			if type(v) in [str, unicode] and self._factory.add_lang:
				v = self.langhash_to_jsonld({self._factory.default_lang : v})
			elif type(v) == dict:
				# "date":{"en:"Circa 1400",fr":"Environ 1400"}
				v = self.langhash_to_jsonld(v)
			self.metadata.append({"label":k, "value":v})

	def set_label(self, label):
		if type(label) in [str, unicode] and self._factory.add_lang:
			label = self.langhash_to_jsonld({self._factory.default_lang : label})
		elif type(label) == dict:
			# {"en:"Something",fr":"Quelque Chose"}
			label = self.langhash_to_jsonld(v)
		self.label = label
				
	def toJSON(self, top=False):
		d = self.__dict__.copy()
		if d.has_key('id') and d['id']:
			d['@id'] = d['id']
			del d['id']
		d['@type'] = d['type']
		del d['type']
		for (k, v) in d.items():
			if not v or k[0] == "_":
				del d[k]
		for e in self._required:
			if not d.has_key(e):
				raise MetadataError("Resource type '%s' requires '%s' to be set" % (self._type, e))
		if self._factory.debug_level == "warn":
			for e in self._warn:
				if not d.has_key(e):
					print "WARNING: Resource type '%s' should have '%s' set" % (self._type, e)

		if top:
			d['@context'] = self._factory.context_uri
		return d

	def toString(self, compact=True):
		js = self.toJSON(top=True)
		if compact:
			return json.dumps(js, sort_keys=True, separators=(',',':'))
		else:
			return json.dumps(js, sort_keys=True, indent=2)



class Manifest(BaseMetadataObject):
	_type = "sc:Manifest"
	_uri_segment = ""
	_required = ["@id", "label", "sequences"]
	_warn = ["description"]
	sequences = []
	structures = []

	def __init__(self, *args, **kw):
		self.sequences = []
		self.structures = []
		return super(Manifest, self).__init__(*args, **kw)

	def add_sequence(self, seq):
		# verify identity doesn't conflict with existing sequences
		if seq.id:
			for s in self.sequences:
				if s.id == seq.id:
					raise MetadataError("Cannot have two Sequences with the same identity")
		self.sequences.append(seq)

	def add_range(self, rng):
		# verify identity doesn't conflict with existing ranges
		if rng.id:
			for r in self.structures:
				if r.id == rng.id:
					raise MetadataError("Cannot have two Ranges with the same identity")
		self.structures.append(rng)

	def sequence(self, *args, **kw):
		seq = self._factory.sequence(*args, **kw)
		self.add_sequence(seq)
		return seq

	def range(self, *args, **kw):
		rng = self._factory.range(*args, **kw)
		self.add_range(rng)
		return rng

	def toJSON(self, top=True):
		json = super(Manifest, self).toJSON(top)
		newseqs = []
		for s in json['sequences']:
			newseqs.append(s.toJSON(False))
		json['sequences'] = newseqs
		if json.has_key('structures'):
			newstructs = []
			for s in json['structures']:
				newstructs.append(s.toJSON(False))
			json['structures'] = newstructs
		return json


class Sequence(BaseMetadataObject):
	_type = "sc:Sequence"
	_uri_segment = "sequence/"
	_required = ["canvases"]
	_warn = ["@id", "label"]
	canvases = []

	def __init__(self, *args, **kw):
		self.canvases = []
		return super(Sequence, self).__init__(*args, **kw)

	def add_canvas(self, cvs):
		if cvs.id:
			for c in self.canvases:
				if c.id == cvs.id:
					raise MetadataError("Cannot have two Canvases with the same identity")
		self.canvases.append(cvs)

	def canvas(self, *args, **kw):
		cvs = self._factory.canvas(*args, **kw)
		self.add_canvas(cvs)
		return cvs

	def toJSON(self, top=True):
		json = super(Sequence, self).toJSON(top)
		newcvs = []
		for c in json['canvases']:
			newcvs.append(c.toJSON(False))
		json['canvases'] = newcvs
		return json

class Canvas(BaseMetadataObject):
	_type = "sc:Canvas"
	_uri_segment = "canvas/"	
	_required = ["@id", "label", "height", "width"]
	_warn = ["images"]
	height = 0
	width = 0
	images = []
	otherContent = []

	def __init__(self, *args, **kw):
		self.images = []
		self.otherContent = []
		self.height = 0
		self.width = 0
		return super(Canvas, self).__init__(*args, **kw)

	def set_hw(self, h,w):
		self.height = h
		self.width = w

	def add_annotation(self, imgAnno):
		self.images.append(imgAnno)
	def add_annotationList(self, annoList):
		self.otherContent.append(annoList)

	def annotation(self, *args, **kw):
		anno = self._factory.annotation(*args, **kw)
		anno.on = self.id
		self.add_annotation(anno)
		return anno

	def annotationList(self, *args, **kw):
		annol = self._factory.annotationList(*args, **kw)
		annol._canvas = self
		self.add_annotationList(annol)
		return annol

	def toJSON(self, top=True):
		json = super(Canvas, self).toJSON(top)
		if json.has_key('images'):
			newimgs = []
			for c in json['images']:
				newimgs.append(c.toJSON(False))
			json['images'] = newimgs
		if json.has_key('otherContent'):
			newlists = []
			for c in json['otherContent']:
				newlists.append(c.toJSON(False))
			json['otherContent'] = newlists
		return json


class Annotation(BaseMetadataObject):
	_type = "oa:Annotation"
	_uri_segment = "annotation/"
	_required = ["motivation", "resource", "on"]
	_warn = ["@id"]

	def __init__(self, *args, **kw):
		self.motivation = "sc:painting"
		self.on = ""
		self.resource = {}
		return super(Annotation, self).__init__(*args, **kw)


	def image(self, ident="", label="", iiif=False):
		img = self._factory.image(ident, label, iiif)
		self.resource = img
		return img

	def text(self, text, language="", format="text/plain"):
		txt = self._factory.text(text, language, format)
		self.resource = txt
		return txt

	def audio(self, ident="", label=""):
		aud = self._factory.audio(ident, label)
		self.resource = aud
		return aud

	def choice(self, default, rest):
		chc = self._factory.choice(default, rest)
		self.resource = chc
		return chc

	def stylesheet(self, css, cls):
		ss = { "@type": ["oa:CssStyle", "cnt:ContentAsText"], "format": "text/css", "chars" : css}
		self.stylesheet = ss
		if not self.resource:
			raise MetadataError("Cannot set a stylesheet without first creating the body")
		if isinstance(self.resource, SpecificResource):
			self.resource.style = cls
		else:
			sr = SpecificResource(self._factory)
			sr.full = self.resource
			sr.style = cls
			self.resource = sr

	def toJSON(self, top=True):
		json = super(Annotation, self).toJSON(top)
		json['resource'] = json['resource'].toJSON(top=False)
		return json


class SpecificResource(BaseMetadataObject):
	_type = "oa:SpecificResource"
	_required = ['full']
	_warn = []
	style = ""
	selector = ""

	def __init__(self, factory):
		self._factory = factory
		self.type = self.__class__._type

	def toJSON(self, top=False):
		json = super(SpecificResource, self).toJSON(top)
		json['full'] = json['full'].toJSON()
		return json

class Text(BaseMetadataObject):
	_type = "cnt:ContentAsText"
	_required = ["chars"]
	_warn = ["format"]
	chars = ""
	format = ""
	language = ""

	def __init__(self, factory, text, language="", format="text/plain"):
		self._factory = factory
		self.type = self.__class__._type
		self.chars = text
		self.format = format
		if language:
			self.language = language

class Audio(BaseMetadataObject):
	_type = "dctypes:Sound"
	_required = ["@id"]
	_warn = ["format"]
	_uri_segment = "res"

class XMLPtr(BaseMetadataObject):
	_type = "dctypes:Text"
	_required = ["@id"]
	_warn = []
	_uri_segment = "res"

	def __init__(self, factory, ident, label="", mdhash={}):
		super(XMLPtr, self).__init__(factory, ident, label, mdhash)
		self.format = "text/xml"


class Image(BaseMetadataObject):
	_type = "dctypes:Image"
	_required = ["@id"]
	_warn = ["format", "height", "width"]

	def __init__(self, factory, ident, label, iiif=False):
		self._factory = factory
		self.type = self.__class__._type
		self.label = ""
		self.format = ""
		self.height = 0
		self.width = 0
		if label:
			self.set_label(label)

		if iiif == True:
			# add IIIF service
			# ident is identifier
			self.id = factory.image_base + ident + '/full/full/0/native.jpg'
			self.format = "image/jpeg"
			self.service = {
				"@id": factory.image_base + ident,
			}
			if factory.iiif_version != -1:
				self.service['profile'] = factory.iiif_profile_uri

		else:
			# Static image
			# ident is either full URL or filename
			if ident.startswith('http://') or ident.startswith('https://'):
				self.id = ident
			else:
				self.id = factory.image_base + ident

	def set_hw(self, h,w):
		self.height = h
		self.width = w

	def set_hw_from_file(self, fn):
		# Try to do it automagically
		if not os.path.exists(fn):
			raise ValueError("Could not find image file: %s" % fn)

		cmd = self._factory.whichid
		if cmd:
			# Try IM
			try:
				info = commands.getoutput(cmd + ' -ping -format "%h %w" ' + fn)
				(h, w) = info.split(" ")
				self.height = int(h)
				self.width = int(w)
				return
			except:
				pass

		if pil_image:
			# Try PIL
			try:
				img = pil_image.open(fn)
				(w,h) = img.size
				self.height = h
				self.width = w
				try:
					img.close()
				except:
					pass
				return
			except:
				pass
		raise ConfigurationError("No identify from ImageMagick and no PIL, you have to set manually")

class Choice(BaseMetadataObject):
	_type = "oa:Choice"
	_uri_segment = "annotation" # not really necessary
	_required = ["item"]
	_warn = ["default"]
	default = {}
	item = []

	def __init__(self, factory, default, rest):
		self.default = default
		if type(rest) != list:
			rest = [rest]
		self.item = rest
		return super(Choice, self).__init__(factory, indent="", label="", mdhash={})


	def toJSON(self, top=True):
		json = super(Choice, self).toJSON(top)
		json['default'] = json['default'].toJSON(top=False)
		newitem = []
		for c in json['item']:
			newitem.append(c.toJSON(False))
		json['item'] = newitem		
		return json

class AnnotationList(BaseMetadataObject):
	_type = "sc:AnnotationList"
	_uri_segment = "list/"	
	_required = ["@id"]
	_warn = []
	_canvas = None
	resources = []

	def __init__(self, *args, **kw):
		self.resources = []
		self._canvas = None
		return super(AnnotationList, self).__init__(*args, **kw)

	def add_annotation(self, imgAnno):
		self.resources.append(imgAnno)

	def annotation(self, *args, **kw):
		anno = self._factory.annotation(*args, **kw)
		if self._canvas:
			anno.on = self._canvas.id
		self.add_annotation(anno)
		return anno

	def toJSON(self, top=True):
		# if top == false, only include @id, @type, label
		# else, include everything
		json = super(AnnotationList, self).toJSON(top)
		if top:
			newl = []
			for c in json['resources']:
				newl.append(c.toJSON(False))
			json['resources'] = newl
		else:
			del json['resources']
		return json


class Range(BaseMetadataObject):
	_type = "sc:Range"
	_uri_segment = "range/"	
	_required = ["@id", "label"]
	_warn = []

class Layer(BaseMetadataObject):
	_type = "sc:Layer"		
	_uri_segment = "layer/"
	_required = ["@id", "label"]
	_warn = []




if __name__ == "__main__":
	factory = ManifestFactory()	
	factory.set_base_metadata_uri("http://www.example.org/metadata/")
	factory.set_base_image_uri("http://www.example.org/iiif/")

	mf = factory.manifest(label="Manifest")
	mf.viewingHint = "paged"

	seq = mf.sequence() 
	for x in range(2):
		# Mostly identity will come from incrementing number (f1r, f1v,...)
		# or the image's identity

		cvs = seq.canvas(ident="c%s" % x, label="Canvas %s" % x)  
		cvs.set_hw(1000,1000)
		anno = cvs.annotation() 
		# al = cvs.annotationList("foo") 

		img = factory.image("f1r.c", iiif=True)
		img.set_hw_from_file("/Users/azaroth/Dropbox/SharedCanvasData/m804/images/f1r.c.jpg")
		img2 = factory.image("f1r", iiif=True)
		img2.set_hw_from_file("/Users/azaroth/Dropbox/SharedCanvasData/m804/images/f1r.jpg")

		chc = anno.choice(img, [img2])








