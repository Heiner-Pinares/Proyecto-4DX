document.querySelector('.password-toggle')?.addEventListener('click', function () {
 const field=document.getElementById('id_password'), show=field.type==='password';
 field.type=show?'text':'password';
 const label=this.querySelector('.password-toggle-label');
 if(label){label.textContent=show?'Ocultar contraseña':'Mostrar contraseña';}else{this.textContent=show?'Ocultar':'Mostrar';}
 this.classList.toggle('is-visible',show);this.setAttribute('aria-label',show?'Ocultar contraseña':'Mostrar contraseña');this.setAttribute('aria-pressed',String(show));
});
document.querySelector('.menu-toggle')?.addEventListener('click', function () {
 const open=document.body.classList.toggle('navigation-open');this.setAttribute('aria-expanded',String(open));
});
