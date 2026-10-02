document.querySelector('.password-toggle')?.addEventListener('click', function () {
 const field=document.getElementById('id_password'), show=field.type==='password';
 field.type=show?'text':'password';this.textContent=show?'Ocultar':'Mostrar';this.setAttribute('aria-label',show?'Ocultar contraseña':'Mostrar contraseña');this.setAttribute('aria-pressed',String(show));
});
document.querySelector('.menu-toggle')?.addEventListener('click', function () {
 const open=document.body.classList.toggle('navigation-open');this.setAttribute('aria-expanded',String(open));
});
