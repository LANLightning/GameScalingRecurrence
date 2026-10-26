from tools.convert.methods import grouped_absmax

def configure(model, recipe, sources):
    # Keep vision weights and small GDN control projections in their original dtype.
    for name,p in model.parameters.items():
        if name.startswith('text/') and p.projection:
            if name.endswith(('/gdn/a_projection','/gdn/b_projection')):
                recipe.separate(name)
            else:
                recipe.assign(name, format='q8_g32_fp16', method=grouped_absmax)
